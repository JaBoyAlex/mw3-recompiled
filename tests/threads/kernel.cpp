// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic callbacks into the actual SDK kernel DLL, not MW3 code.
#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <rex/app/app.h>
#include <rex/kernel/export.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/heap.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/types/status.h>
#include <rex/kernel/types/list.h>
#include <rex/logging/logger.h>
#include <rex/logging/log_category.h>
#include <rex/kernel/types/thread.h>
#include <rex/ppc/image.h>
#include <rex/ppc/call.h>
#include "kernel/test_access.h" // Exported upstream seam for real-DLL resource inspection.
#include "kernel/guest_stack.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <memory>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace k=rex::kernel;
using u32=std::uint32_t;using u64=std::uint64_t;
namespace {
struct Failure : std::runtime_error {using std::runtime_error::runtime_error;};
void Check(bool value,const char* why) {if(!value) throw Failure(why);}
template<class T> void Ok(const T& value,const char* why) {Check(bool(value),why);}
constexpr u32 code=0x82090000,entry=code+0x1000,child_entry=code+0x2000,cookie=0x4d573339;
struct State {
  std::function<void(PPCContext&,u8*)> body,child;
  std::atomic<bool> completed=false,armed=false,returned=false;
  std::atomic<unsigned> child_failures=0;
  std::string failure;
};
std::atomic<State*> active=nullptr;
void Entry(PPCContext& ctx,u8* base) {
  auto* state=active.load(std::memory_order_acquire);
  if(!state) {std::fputs("THREAD_MISSING_OWNED_STATE\n",stderr);std::_Exit(3);}
  try {
    state->body(ctx,base);ctx.r3.u64=0;
    state->completed.store(true,std::memory_order_release);
  } catch(const Failure& e) {
    state->failure=e.what();state->completed.store(true,std::memory_order_release);
  }
  // SDK ThreadStop must unwind to its own entry; do not catch it here.
}
void ChildEntry(PPCContext& ctx,u8* base) {
  auto* state=active.load(std::memory_order_acquire);
  if(!state) {std::fputs("THREAD_MISSING_CHILD_STATE\n",stderr);std::_Exit(3);}
  try {state->child(ctx,base);ctx.r3.u64=0;}
  catch(const Failure& e) {++state->child_failures;std::fprintf(stderr,"THREAD_CHILD_FAILURE:%s\n",e.what());ctx.r3.u64=1;}
  catch(const rex::ThreadStop& stop) {
    std::fprintf(stderr,"THREAD_CHILD_STOP exit=%d\n",stop.exit_code);throw;
  }
}
const PPCFuncMapping mappings[]={{entry,&Entry},{child_entry,&ChildEntry},{0,nullptr}};
const rex::ppc::PPCImage image{code,0x10000,0x82000000,0x100000,mappings};
struct TestApp : rex::app::App {TestApp():App("mw3_thread_contract") {}};
u32 Call(PPCContext& ctx,u8* base,std::string_view name,std::initializer_list<u64> args,
         k::ExportModule module=k::ExportModule::kXboxkrnl) {
  const auto exports=k::GetExports(module);
  auto found=std::find_if(exports.begin(),exports.end(),[&](const auto& e){return e.name==name;});
  if(found==exports.end() || !found->fn) throw Failure("unknown kernel function in synthetic contract: "+std::string(name));
  PPCRegister* registers[]={&ctx.r3,&ctx.r4,&ctx.r5,&ctx.r6,&ctx.r7,&ctx.r8,&ctx.r9,&ctx.r10};
  Check(args.size()<=8,"synthetic export call exceeds register argument contract");
  unsigned n=0;for(auto value:args) registers[n++]->u64=value;
  found->fn(ctx,base);return ctx.r3.u32;
}
struct Fixture {
  TestApp app;
  std::unique_ptr<k::TitleRuntime> runtime;
  std::vector<u32> handles;
  bool finished=false;
  explicit Fixture(unsigned cycle) {
    const auto root=std::filesystem::current_path()/("kernel-profile-"+std::to_string(cycle));
    std::filesystem::create_directories(root);
    const std::vector<std::string> flags={"--app.root="+(root/"app").string(),"--app.user_root="+(root/"user").string(),
      "--title.game_root="+root.string(),"--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"};
    Ok(app.Init(rex::CLIArgList::Parse(flags)),"synthetic app initialization failed");
    runtime=std::make_unique<k::TitleRuntime>(image);
    Ok(runtime->GetTitlePaths().entry.Set(""),"synthetic empty entry rejected");
    Ok(runtime->Load(),"synthetic runtime load failed");
  }
  void Finish() {
    runtime->Unload();Check(!runtime->IsLoaded(),"synthetic runtime remained loaded");
    runtime.reset();app.Shutdown();finished=true;
  }
  ~Fixture() {
    if(!finished) {
      try {if(runtime) {runtime->Unload();runtime.reset();}app.Shutdown();}
      catch(...) {std::fputs("THREAD_RUNTIME_CLEANUP_FAILED\n",stderr);std::fflush(stderr);std::_Exit(3);}
    }
  }
  void Run(State& state,bool suspended=false,bool termination=false,u32 expected_exit=42) {
    State* empty=nullptr;
    Check(active.compare_exchange_strong(empty,&state),"overlapping synthetic contract state");
    struct Binding {~Binding(){active.store(nullptr,std::memory_order_release);}} binding;
    const auto before=runtime->GetObjectTable().GetAll().size();
    const auto pages_before=k::GetAddressSpace(*runtime).GetTitlePages();
    auto worker=std::make_unique<k::KernelThread>(*runtime,0x10000,0,entry,cookie,suspended?1:0,true,false);
    auto created=runtime->GetThreadRegistry().Launch(std::move(worker));Ok(created,"guest thread launch failed");
    const u32 handle=*created;
    if(suspended) {
      auto pin=runtime->GetThreadRegistry().FindByHandle(handle);Ok(pin,"suspended guest handle missing");
      Check(pin->GetSuspendCount()==1,"initial guest suspend count wrong");
      u32 previous=0;
      Check(pin->Suspend(&previous)==0 && previous==1,"guest nested suspend failed");
      Check(pin->Resume(&previous)==0 && previous==2,"guest first resume count wrong");
      Check(pin->GetSuspendCount()==1,"guest resumed before count reached zero");
      Check(pin->Resume(&previous)==0 && previous==1,"guest final resume count wrong");
    }
    u64 timeout=u64(-std::int64_t{100000000});
    if(runtime->GetThreadRegistry().GetObjectWaiter().WaitGuestObject(handle,0,0,0,&timeout)!=0) {
      std::fputs("THREAD_RUNTIME_OWNED_DEADLINE\n",stderr);std::fflush(stderr);std::_Exit(3);
    }
    const bool completed=state.completed.load(std::memory_order_acquire);
    auto pin=runtime->GetThreadRegistry().FindByHandle(handle);Ok(pin,"completed guest handle missing");
    auto object=runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"completed guest object unreadable");
    const bool status=object->terminated==1 && object->exit_status==(termination?expected_exit:0u);
    pin.Reset();k::CloseOwned(runtime->GetObjectTable(),handle);
    for(auto leftover:handles) k::CloseOwned(runtime->GetObjectTable(),leftover);
    const bool no_leaks=handles.empty();handles.clear();active.store(nullptr,std::memory_order_release);
    if(completed && !state.failure.empty()) throw Failure(state.failure);
    Check(state.child_failures.load()==0,"guest child contract failed");
    Check(status,"guest termination metadata/exit status wrong");
    Check(termination?(!completed && state.armed.load() && !state.returned.load()):completed,"guest callback completion contract wrong");
    Check(no_leaks,"kernel contract left owned handles open");
    Check(runtime->GetObjectTable().GetAll().size()==before,"kernel handle accounting did not recover");
    Check(k::GetAddressSpace(*runtime).GetTitlePages()==pages_before,"kernel title-page accounting did not recover");
    std::printf("THREAD_ACCOUNT handles=%zu pages_before=%u pages_after=%u\n",before,pages_before,
      k::GetAddressSpace(*runtime).GetTitlePages());
  }
};
void Context(k::TitleRuntime& runtime,PPCContext& ctx,u32 expected_cookie=cookie) {
  Check(ctx.r3.u32==expected_cookie,"guest startup cookie wrong");
  auto* thread=k::KernelThread::GetCallingThread();Check(thread && thread->GetPCRPtr()==ctx.r13.u32,"guest r13/PCR binding wrong");
  auto pcr=runtime.GetGuestMemory().Load<k::X_KPCR>(ctx.r13.u32);Ok(pcr,"PCR unreadable");
  Check(pcr->pcr_ptr==ctx.r13.u64,"PCR self address wrong");
  Check(pcr->stack_end_ptr<ctx.r1.u32 && ctx.r1.u32<pcr->stack_base_ptr && ctx.r1.u32%16==0,"guest stack bounds/alignment wrong");
  k::HeapAllocation allocation{};
  auto* heap=thread->GetAddressSpace()->LookupHeap(pcr->stack_end_ptr);
  Check(heap && heap->QueryRegionInfo(pcr->stack_end_ptr,&allocation),"guest stack allocation query failed");
  const u32 guard=allocation.allocation_base;
  // TLS can add committed alignment padding below PCR.stack_end_ptr. The
  // protected guard is the first page of the owned stack allocation.
  Check(guard%k::kGuestStackPageSize==0 && guard+k::kGuestStackPageSize<=pcr->stack_end_ptr,"guest guard layout invalid");
  Check(!runtime.GetGuestMemory().GetReadOnlySpan(guard,k::kGuestStackPageSize),"guest stack guard readable");
  Check(!runtime.GetGuestMemory().GetReadOnlySpan(guard+k::kGuestStackPageSize-1,1),"guest stack guard end readable");
  std::printf("THREAD_STACK allocation=%08x limit=%08x top=%08x\n",guard,u32(pcr->stack_end_ptr),u32(pcr->stack_base_ptr));
}
u32 RequestStopInsideThunk(u32 exit) {
  k::KernelThread::GetCallingThread()->RequestStop(static_cast<std::int32_t>(exit));
  return 0x5a;
}
}

TEST_CASE("original kernel: a stop after a native thunk body preserves the requested exit", "[mw3][kernel][cancel][boundary]") {
  State state;Fixture fixture(0);
  state.body=[&](PPCContext& ctx,u8* base) {
    Context(*fixture.runtime,ctx);state.armed.store(true,std::memory_order_release);
    ctx.r3.u32=77;
    rex::ppc::GuestToHostThunk<&RequestStopInsideThunk>(ctx,base);
    state.returned.store(true,std::memory_order_release);
  };
  REQUIRE_NOTHROW(fixture.Run(state,false,true,77));REQUIRE_NOTHROW(fixture.Finish());
}

TEST_CASE("original kernel: an explicit exit keeps its value despite a pending stop", "[mw3][kernel][exit]") {
  unsigned cycle=0;
  for(const std::int32_t exit:{0,42,-17,std::numeric_limits<std::int32_t>::min()}) {
    State state;Fixture fixture(cycle++);
    state.body=[&](PPCContext& ctx,u8*) {
      Context(*fixture.runtime,ctx);state.armed.store(true,std::memory_order_release);
      auto* thread=k::KernelThread::GetCallingThread();thread->RequestStop(77);
      thread->Exit(exit);state.returned.store(true,std::memory_order_release);
    };
    REQUIRE_NOTHROW(fixture.Run(state,false,true,static_cast<u32>(exit)));
    REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original kernel: guest context and object semantics survive repeated teardown", "[mw3][kernel]") {
  for(unsigned cycle=0;cycle<4;++cycle) {
    State state;Fixture fixture(cycle);
    auto allocation=fixture.runtime->GetGuestMemory().Allocate(0x10000,0x1000,k::GuestProtect::kReadWrite);
    Ok(allocation,"contract scratch allocation failed");const u32 scratch=*allocation;
    state.body=[&](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);auto view=fixture.runtime->GetGuestMemory().GetView();
      view.Store<u64>(scratch+32,0); // Polling timeout, big endian guest bytes.
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      auto take=[&]{const auto h=view.Load<u32>(scratch);fixture.handles.push_back(h);return h;};
      auto close=[&](u32 h){Check(call("NtClose",{h})==0,"kernel close failed");std::erase(fixture.handles,h);};
      auto wait=[&](u32 h){return call("NtWaitForSingleObjectEx",{h,1,0,scratch+32});};
      Check(call("NtCreateSemaphore",{scratch,0,1,2})==0,"kernel semaphore create failed");const auto sem=take();
      Check(wait(sem)==0 && wait(sem)==k::X_STATUS_TIMEOUT,"kernel semaphore consumption wrong");
      Check(call("NtReleaseSemaphore",{sem,2,scratch+8})==0 && view.Load<u32>(scratch+8)==0,"kernel semaphore release accounting wrong");
      Check(call("NtReleaseSemaphore",{sem,1,0})==k::X_STATUS_SEMAPHORE_LIMIT_EXCEEDED,"kernel semaphore limit ignored");
      Check(wait(sem)==0 && wait(sem)==0 && wait(sem)==k::X_STATUS_TIMEOUT,"kernel semaphore excess release mutated count");
      close(sem);Check(wait(sem)==k::X_STATUS_INVALID_HANDLE,"closed semaphore remained valid");
      for(u32 kind:{0u,1u}) {
        Check(call("NtCreateEvent",{scratch,0,kind,0})==0,"kernel event create failed");const auto event=take();
        Check(wait(event)==k::X_STATUS_TIMEOUT,"new event already signaled");
        Check(call("NtSetEvent",{event,scratch+8})==0,"kernel event set failed");
        Check(wait(event)==0,"signaled event did not wake");
        Check(wait(event)==(kind?k::X_STATUS_TIMEOUT:0),"kernel event reset policy wrong");
        Check(call("NtClearEvent",{event})==0 && wait(event)==k::X_STATUS_TIMEOUT,"kernel event reset failed");close(event);
      }
      Check(call("NtCreateMutant",{scratch,0,1})==0,"kernel mutex create failed");const auto mutex=take();
      Check(wait(mutex)==0,"kernel recursive mutex acquisition failed");
      Check(call("NtReleaseMutant",{mutex,0})==0 && call("NtReleaseMutant",{mutex,0})==0,"kernel recursive mutex release failed");
      Check(call("NtReleaseMutant",{mutex,0})==k::X_STATUS_MUTANT_NOT_OWNED,"kernel mutex accepted unowned release");close(mutex);
    };
    REQUIRE_NOTHROW(fixture.Run(state,true));Ok(fixture.runtime->GetGuestMemory().Free(scratch),"scratch release failed");
    REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original kernel: self termination preserves the requested exit and never returns", "[mw3][kernel]") {
  for(unsigned cycle=0;cycle<4;++cycle) {
    State state;Fixture fixture(cycle);
    state.body=[&](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);state.armed.store(true,std::memory_order_release);
      Call(ctx,base,"ExTerminateThread",{42});state.returned.store(true,std::memory_order_release);
    };
    REQUIRE_NOTHROW(fixture.Run(state,false,true));REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original kernel: concurrent guest TLS is isolated and free clears every live slot", "[mw3][kernel][tls]") {
  for(unsigned cycle=0;cycle<4;++cycle) {
    std::array<std::atomic<u32>,8> pcrs{},phases{};
    std::array<u32,8> children{};
    u32 slot=0,ready=0,first_gate=0,second_gate=0;
    State configure,state;Fixture fixture(cycle);
    configure.body=[&](PPCContext& ctx,u8*) {
      Context(*fixture.runtime,ctx);
      auto* thread=k::KernelThread::GetCallingThread();
      const auto process_address=static_cast<u32>(thread->GetGuestObject<k::X_KTHREAD>()->process);
      auto* process=thread->GetAddressSpace()->TranslateVirtual<k::X_KPROCESS*>(process_address);
      Check(process!=nullptr,"synthetic title process missing");
      // Original empty-image fixture has no TLS header. Configure its owned
      // process before creating the threads whose TLS blocks are measured.
      process->tls_slot_size=16;
      for(unsigned i=0;i<8;++i) process->tls_slot_bitmap[i]=i==0?0xf0000000u:0;
    };
    REQUIRE_NOTHROW(fixture.Run(configure));
    auto allocation=fixture.runtime->GetGuestMemory().Allocate(0x10000,0x1000,k::GuestProtect::kReadWrite);
    Ok(allocation,"TLS contract scratch allocation failed");const u32 scratch=*allocation;
    state.child=[&,scratch](PPCContext& ctx,u8* base) {
      const u32 id=ctx.r3.u32;Check(id>=1 && id<=8,"child startup index wrong");
      Context(*fixture.runtime,ctx,id);const auto index=id-1;
      pcrs[index].store(ctx.r13.u32,std::memory_order_release);
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      Check(call("KeTlsGetValue",{slot})==0,"new guest TLS slot was not zero");
      Check(call("KeTlsSetValue",{slot,0x100+id})==1,"guest TLS write failed");
      Check(call("NtReleaseSemaphore",{ready,1,0})==0,"first child barrier failed");
      Check(call("NtWaitForSingleObjectEx",{first_gate,1,0,scratch+32})==0,"first guest TLS gate failed");
      for(unsigned repeat=0;repeat<128;++repeat)
        Check(call("KeTlsGetValue",{slot})==0x100+id,"guest TLS value crossed threads");
      phases[index].store(1,std::memory_order_release);
      Check(call("NtReleaseSemaphore",{ready,1,0})==0,"second child barrier failed");
      Check(call("NtWaitForSingleObjectEx",{second_gate,1,0,scratch+32})==0,"second guest TLS gate failed");
      Check(call("KeTlsGetValue",{slot})==0,"freed live guest TLS slot retained its value");
      phases[index].store(2,std::memory_order_release);
    };
    state.body=[&,scratch](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);auto view=fixture.runtime->GetGuestMemory().GetView();
      view.Store<u64>(scratch+32,u64(-std::int64_t{50000000}));
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      auto take=[&]{auto h=view.Load<u32>(scratch);fixture.handles.push_back(h);return h;};
      auto close=[&](u32 h){Check(call("NtClose",{h})==0,"TLS contract close failed");std::erase(fixture.handles,h);};
      std::array<u32,4> slots{};
      for(u32 i=0;i<4;++i) {slots[i]=call("KeTlsAlloc",{});Check(slots[i]==i,"guest TLS slot allocation order wrong");}
      Check(call("KeTlsAlloc",{})==0xffffffffu,"guest TLS slot exhaustion ignored");slot=slots[0];
      for(unsigned i=1;i<4;++i) Check(call("KeTlsFree",{slots[i]})==1,"extra guest TLS slot release failed");
      Check(call("KeTlsSetValue",{slot,0x55})==1,"main guest TLS write failed");
      Check(call("NtCreateSemaphore",{scratch,0,0,8})==0,"TLS barrier create failed");ready=take();
      Check(call("NtCreateEvent",{scratch,0,0,0})==0,"first TLS gate create failed");first_gate=take();
      Check(call("NtCreateEvent",{scratch,0,0,0})==0,"second TLS gate create failed");second_gate=take();
      for(unsigned i=0;i<8;++i) {
        Check(call("ExCreateThread",{scratch,0x10000,0,0,child_entry,i+1,0})==0,"guest TLS child creation failed");children[i]=take();
      }
      auto wait_ready=[&]{for(unsigned i=0;i<8;++i)
        Check(call("NtWaitForSingleObjectEx",{ready,1,0,scratch+32})==0,"guest TLS readiness deadline");};
      wait_ready();
      for(unsigned i=0;i<8;++i) {
        auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(children[i]);Ok(pin,"live TLS child handle missing");
        Check(pin->GetPCRPtr()==pcrs[i].load(std::memory_order_acquire),"guest child identity/PCR mismatch");
        for(unsigned j=0;j<i;++j) Check(pcrs[i].load()!=pcrs[j].load(),"concurrent guest threads share PCR");
      }
      Check(call("KeTlsGetValue",{slot})==0x55,"children changed main guest TLS");
      Check(call("NtSetEvent",{first_gate,0})==0,"first TLS gate release failed");wait_ready();
      for(const auto& phase:phases) Check(phase.load(std::memory_order_acquire)==1,"child did not verify private TLS");
      Check(call("KeTlsFree",{slot})==1 && call("KeTlsGetValue",{slot})==0,"main TLS free/clear failed");
      Check(call("NtSetEvent",{second_gate,0})==0,"second TLS gate release failed");
      for(unsigned i=0;i<8;++i) {
        Check(call("NtWaitForSingleObjectEx",{children[i],1,0,scratch+32})==0,"guest TLS child join deadline");
        auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(children[i]);Ok(pin,"completed TLS child missing");
        auto object=fixture.runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"TLS child metadata unreadable");
        Check(object->terminated==1 && object->exit_status==0,"TLS child exit status wrong");pin.Reset();close(children[i]);
        Check(phases[i].load(std::memory_order_acquire)==2,"child did not verify live TLS clearing");
      }
      close(first_gate);close(second_gate);close(ready);
    };
    REQUIRE_NOTHROW(fixture.Run(state));
    Ok(fixture.runtime->GetGuestMemory().Free(scratch),"TLS scratch release failed");REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original kernel: a stop wakes a blocked guest wait with its requested exit", "[mw3][kernel][cancel]") {
  const std::string negative=std::getenv("MW3_THREAD_NEGATIVE")?std::getenv("MW3_THREAD_NEGATIVE"):"";
  for(unsigned cycle=0;cycle<4;++cycle) {
    u32 ready=0,gate=0,child=0;std::atomic<bool> returned=false;
    State state;Fixture fixture(cycle);
    auto allocation=fixture.runtime->GetGuestMemory().Allocate(0x10000,0x1000,k::GuestProtect::kReadWrite);
    Ok(allocation,"cancel scratch allocation failed");const u32 scratch=*allocation;
    state.child=[&,scratch](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx,1);
      Check(Call(ctx,base,"NtReleaseSemaphore",{ready,1,0})==0,"cancel readiness signal failed");
      // An infinite guest wait must be woken by RequestStop, not its timeout.
      const auto status=Call(ctx,base,"NtWaitForSingleObjectEx",{gate,1,0,0});
      returned.store(true,std::memory_order_release);
      Check(negative=="deadline" && status==0,"cancellable guest wait unexpectedly returned");
    };
    state.body=[&,scratch](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);auto view=fixture.runtime->GetGuestMemory().GetView();
      view.Store<u64>(scratch+32,u64(-std::int64_t{50000000}));
      view.Store<u64>(scratch+40,u64(-std::int64_t{2000000}));
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      auto take=[&]{const auto h=view.Load<u32>(scratch);fixture.handles.push_back(h);return h;};
      auto close=[&](u32 h){Check(call("NtClose",{h})==0,"cancel object close failed");std::erase(fixture.handles,h);};
      Check(call("NtCreateSemaphore",{scratch,0,0,1})==0,"cancel barrier create failed");ready=take();
      Check(call("NtCreateEvent",{scratch,0,0,0})==0,"cancel gate create failed");gate=take();
      Check(call("ExCreateThread",{scratch,0x10000,0,0,child_entry,1,0})==0,"cancel child create failed");child=take();
      Check(call("NtWaitForSingleObjectEx",{ready,1,0,scratch+32})==0,"cancel readiness deadline");
      bool missing_wake_detected=false;
      if(negative=="deadline") {
        std::puts("THREAD_DEADLINE_NEGATIVE_ARMED");std::fflush(stdout);
        missing_wake_detected=call("NtWaitForSingleObjectEx",{child,1,0,scratch+40})==k::X_STATUS_TIMEOUT;
        Check(call("NtSetEvent",{gate,0})==0,"negative deadline cleanup release failed");
      } else {
        auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(child);Ok(pin,"cancel target missing");
        pin->RequestStop(77);
      }
      Check(call("NtWaitForSingleObjectEx",{child,1,0,scratch+32})==0,"cancelled child join deadline");
      auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(child);Ok(pin,"cancelled child metadata missing");
      auto object=fixture.runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"cancelled child unreadable");
      const u32 actual_exit=object->exit_status;Check(object->terminated==1,"cancelled child not terminated");pin.Reset();
      std::printf("THREAD_CANCEL exit=%u returned=%u\n",actual_exit,unsigned(returned.load(std::memory_order_acquire)));
      close(child);close(gate);close(ready);
      if(negative=="result") Check(actual_exit==78,"THREAD_RESULT_MUTATION_DETECTED");
      else if(negative=="deadline") {
        Check(actual_exit==0 && returned.load(std::memory_order_acquire),"negative deadline cleanup did not complete");
        Check(!missing_wake_detected,"THREAD_DEADLINE_MUTATION_DETECTED");
      } else Check(actual_exit==77 && !returned.load(std::memory_order_acquire),"stop did not unwind with the requested exit");
    };
    REQUIRE_NOTHROW(fixture.Run(state));
    Ok(fixture.runtime->GetGuestMemory().Free(scratch),"cancel scratch release failed");REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original kernel: a pending stop at an import preserves the requested exit", "[mw3][kernel][cancel][boundary]") {
  const bool use_xam=GENERATE(false,true);
  auto gate=rex::platform::Event::CreateManualResetEvent(false);REQUIRE(gate);
  std::atomic<bool> returned=false;
  u32 ready=0,child=0;State state;Fixture fixture(0);
  auto allocation=fixture.runtime->GetGuestMemory().Allocate(0x10000,0x1000,k::GuestProtect::kReadWrite);
  Ok(allocation,"boundary scratch allocation failed");const u32 scratch=*allocation;
  state.child=[&](PPCContext& ctx,u8* base) {
    Context(*fixture.runtime,ctx,1);
    Check(Call(ctx,base,"NtReleaseSemaphore",{ready,1,0})==0,"boundary readiness signal failed");
    // Native-only fixture barrier deliberately holds the child outside the
    // guest thunk until RequestStop has completed. No sleep or scheduler guess.
    Check(rex::platform::Wait(gate.get(),false,std::chrono::seconds(3))==rex::platform::WaitResult::kSuccess,"boundary host gate deadline");
    if(use_xam) Call(ctx,base,"XGetLanguage",{},k::ExportModule::kXAM);
    else Call(ctx,base,"NtYieldExecution",{});
    returned.store(true,std::memory_order_release);
  };
  state.body=[&](PPCContext& ctx,u8* base) {
    Context(*fixture.runtime,ctx);auto view=fixture.runtime->GetGuestMemory().GetView();
    view.Store<u64>(scratch+32,u64(-std::int64_t{50000000}));
    Check(Call(ctx,base,"NtCreateSemaphore",{scratch,0,0,1})==0,"boundary barrier create failed");
    ready=view.Load<u32>(scratch);fixture.handles.push_back(ready);
    Check(Call(ctx,base,"ExCreateThread",{scratch,0x10000,0,0,child_entry,1,0})==0,"boundary child create failed");
    child=view.Load<u32>(scratch);fixture.handles.push_back(child);
    Check(Call(ctx,base,"NtWaitForSingleObjectEx",{ready,1,0,scratch+32})==0,"boundary readiness deadline");
    {auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(child);Ok(pin,"boundary child missing");pin->RequestStop(77);}
    gate->Set();
    Check(Call(ctx,base,"NtWaitForSingleObjectEx",{child,1,0,scratch+32})==0,"boundary child join deadline");
    auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(child);Ok(pin,"boundary completed child missing");
    auto object=fixture.runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"boundary exit metadata missing");
    const u32 actual=object->exit_status;Check(object->terminated==1,"boundary child still running");pin.Reset();
    for(auto handle:{child,ready}) {Check(Call(ctx,base,"NtClose",{handle})==0,"boundary close failed");std::erase(fixture.handles,handle);}
    std::printf("THREAD_BOUNDARY_STOP service=%s requested=77 actual=%u returned=%u\n",
      use_xam?"XGetLanguage":"NtYieldExecution",actual,unsigned(returned.load()));
    Check(actual==77 && !returned.load(std::memory_order_acquire),"pending stop lost its requested exit at an import boundary");
  };
  REQUIRE_NOTHROW(fixture.Run(state));Ok(fixture.runtime->GetGuestMemory().Free(scratch),"boundary scratch release failed");
  REQUIRE_NOTHROW(fixture.Finish());
}

TEST_CASE("original kernel: concurrent interlocked lists publish each seeded payload once", "[mw3][kernel][interlocked]") {
  constexpr unsigned workers=4,per_worker=128,total=workers*per_worker;
  for(unsigned cycle=0;cycle<3;++cycle) {
    std::array<std::atomic<unsigned>,total> seen{};
    std::array<u32,total> payloads{};std::array<u32,workers> children{};
    std::atomic<u64> sum=0;u64 expected=0;
    u32 seed=std::array<u32,3>{1,0x12345678,0xffffffff}[cycle],ready=0,gate=0;
    for(auto& value:payloads) {seed=seed*1664525u+1013904223u;value=seed;expected+=value;}
    State state;Fixture fixture(cycle);
    auto allocation=fixture.runtime->GetGuestMemory().Allocate(0x10000,0x1000,k::GuestProtect::kReadWrite);
    Ok(allocation,"interlocked scratch allocation failed");const u32 scratch=*allocation,header=scratch+128,nodes=scratch+0x1000;
    auto view=fixture.runtime->GetGuestMemory().GetView();view.Store<u64>(header,0);
    for(unsigned i=0;i<total;++i) {
      const u32 at=nodes+i*16;view.Store<u32>(at,0);view.Store<u32>(at+4,payloads[i]);
      view.Store<u32>(at+8,~payloads[i]);view.Store<u32>(at+12,0xa53c0000u^i);
    }
    state.child=[&,scratch,header,nodes](PPCContext& ctx,u8* base) {
      const u32 id=ctx.r3.u32;Check(id>=1 && id<=workers,"interlocked child index wrong");Context(*fixture.runtime,ctx,id);
      auto memory=fixture.runtime->GetGuestMemory().GetView();
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      for(unsigned i=(id-1)*per_worker;i<id*per_worker;++i) {
        const auto old=call("InterlockedPushEntrySList",{header,nodes+i*16});
        Check(!old || (old>=nodes && old<nodes+total*16 && (old-nodes)%16==0),"interlocked push returned foreign head");
      }
      Check(call("NtReleaseSemaphore",{ready,1,0})==0,"interlocked producer barrier failed");
      Check(call("NtWaitForSingleObjectEx",{gate,1,0,scratch+32})==0,"interlocked consumer gate deadline");
      for(;;) {
        const u32 at=call("InterlockedPopEntrySList",{header});if(!at) break;
        Check(at>=nodes && at<nodes+total*16 && (at-nodes)%16==0,"interlocked pop returned foreign node");
        const unsigned index=(at-nodes)/16;const auto value=memory.Load<u32>(at+4);
        Check(value==payloads[index] && memory.Load<u32>(at+8)==~value && memory.Load<u32>(at+12)==(0xa53c0000u^index),"interlocked payload publication corrupt");
        Check(seen[index].fetch_add(1,std::memory_order_relaxed)==0,"interlocked node popped twice");sum.fetch_add(value,std::memory_order_relaxed);
      }
    };
    state.body=[&,scratch,header](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);auto memory=fixture.runtime->GetGuestMemory().GetView();
      memory.Store<u64>(scratch+32,u64(-std::int64_t{50000000}));
      auto call=[&](std::string_view name,std::initializer_list<u64> args){return Call(ctx,base,name,args);};
      auto take=[&]{const auto h=memory.Load<u32>(scratch);fixture.handles.push_back(h);return h;};
      auto close=[&](u32 h){Check(call("NtClose",{h})==0,"interlocked close failed");std::erase(fixture.handles,h);};
      Check(call("NtCreateSemaphore",{scratch,0,0,workers})==0,"interlocked barrier create failed");ready=take();
      Check(call("NtCreateEvent",{scratch,0,0,0})==0,"interlocked gate create failed");gate=take();
      for(unsigned i=0;i<workers;++i) {
        Check(call("ExCreateThread",{scratch,0x10000,0,0,child_entry,i+1,0})==0,"interlocked child create failed");children[i]=take();
      }
      for(unsigned i=0;i<workers;++i) Check(call("NtWaitForSingleObjectEx",{ready,1,0,scratch+32})==0,"interlocked readiness deadline");
      Check(memory.Load<rex::u16>(header+offsetof(k::X_SLIST_HEADER,depth))==total,"interlocked pushed depth wrong");
      Check(call("NtSetEvent",{gate,0})==0,"interlocked consumer gate release failed");
      for(auto child:children) {
        Check(call("NtWaitForSingleObjectEx",{child,1,0,scratch+32})==0,"interlocked child join deadline");
        auto pin=fixture.runtime->GetThreadRegistry().FindByHandle(child);Ok(pin,"interlocked child metadata missing");
        auto object=fixture.runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"interlocked child unreadable");
        Check(object->terminated==1 && object->exit_status==0,"interlocked child exit wrong");pin.Reset();close(child);
      }
      for(const auto& count:seen) Check(count.load()==1,"interlocked list lost a node");
      Check(sum.load()==expected,"interlocked payload sum wrong");
      Check(memory.Load<rex::u16>(header+offsetof(k::X_SLIST_HEADER,depth))==0,"interlocked empty depth wrong");
      Check(call("InterlockedPopEntrySList",{header})==0 && call("InterlockedFlushSList",{header})==0,"empty interlocked list was not empty");
      close(gate);close(ready);
    };
    REQUIRE_NOTHROW(fixture.Run(state));Ok(fixture.runtime->GetGuestMemory().Free(scratch),"interlocked scratch release failed");
    REQUIRE_NOTHROW(fixture.Finish());
  }
}

TEST_CASE("original diagnostics: exited callback is quiet after the capture history cursor", "[mw3][kernel][diagnostics]") {
  Fixture fixture(0);
  REXLOG_WARN("THREAD_DIAGNOSTIC_RETAINED_WARNING");
  auto thread=rex::platform::Thread::Create({},[]{});REQUIRE(thread);
  REQUIRE(rex::platform::Wait(thread.get(),false,std::chrono::seconds(3))==rex::platform::WaitResult::kSuccess);
  rex::log::LogCaptureSink sink;auto guard=REX_LOGGER().AddSink(sink);
  std::vector<rex::log::CapturedMessage> history;
  const auto cursor=sink.CopySince(0,history);
  REQUIRE(std::ranges::any_of(history,[](const auto& m){return m.text=="THREAD_DIAGNOSTIC_RETAINED_WARNING";}));
  auto ran=std::make_shared<std::atomic<bool>>(false);auto token=std::make_shared<int>(7);std::weak_ptr<int> alive=token;
  thread->QueueUserCallback([ran,token=std::move(token)]{ran->store(true);});
  std::vector<rex::log::CapturedMessage> fresh;sink.CopySince(cursor,fresh);guard.Reset();
  CHECK(alive.expired());CHECK_FALSE(ran->load());
  for(const auto& message:fresh) INFO(message.text);
  CHECK(std::ranges::none_of(fresh,[](const auto& m){return m.level>=rex::log::Level::kWarn;}));
  thread.reset();REQUIRE_NOTHROW(fixture.Finish());
}
