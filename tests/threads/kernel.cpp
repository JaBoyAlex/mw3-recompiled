// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic callbacks into the actual SDK kernel DLL, not MW3 code.
#include <catch2/catch_test_macros.hpp>
#include <rex/app/app.h>
#include <rex/kernel/export.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/heap.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/types/status.h>
#include <rex/kernel/types/thread.h>
#include <rex/ppc/image.h>
#include "kernel/test_access.h" // Exported upstream seam for real-DLL resource inspection.
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <filesystem>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace k=rex::kernel;
using u32=std::uint32_t;using u64=std::uint64_t;
namespace {
struct Failure : std::runtime_error {using std::runtime_error::runtime_error;};
void Check(bool value,const char* why) {if(!value) throw Failure(why);}
template<class T> void Ok(const T& value,const char* why) {Check(bool(value),why);}
constexpr u32 code=0x82090000,entry=code+0x1000,cookie=0x4d573339;
struct State {
  std::function<void(PPCContext&,u8*)> body;
  std::atomic<bool> completed=false,armed=false,returned=false;
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
const PPCFuncMapping mappings[]={{entry,&Entry},{0,nullptr}};
const rex::ppc::PPCImage image{code,0x10000,0x82000000,0x100000,mappings};
struct TestApp : rex::app::App {TestApp():App("mw3_thread_contract") {}};
u32 Call(PPCContext& ctx,u8* base,std::string_view name,std::initializer_list<u64> args) {
  const auto exports=k::GetExports(k::ExportModule::kXboxkrnl);
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
  void Run(State& state,bool suspended=false,bool termination=false) {
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
    const bool status=object->terminated==1 && object->exit_status==(termination?42u:0u);
    pin.Reset();k::CloseOwned(runtime->GetObjectTable(),handle);
    for(auto leftover:handles) k::CloseOwned(runtime->GetObjectTable(),leftover);
    const bool no_leaks=handles.empty();handles.clear();active.store(nullptr,std::memory_order_release);
    if(completed && !state.failure.empty()) throw Failure(state.failure);
    Check(status,"guest termination metadata/exit status wrong");
    Check(termination?(!completed && state.armed.load() && !state.returned.load()):completed,"guest callback completion contract wrong");
    Check(no_leaks,"kernel contract left owned handles open");
    Check(runtime->GetObjectTable().GetAll().size()==before,"kernel handle accounting did not recover");
    std::printf("THREAD_ACCOUNT handles=%zu pages_before=%u pages_after=%u\n",before,pages_before,
      k::GetAddressSpace(*runtime).GetTitlePages());
  }
};
void Context(k::TitleRuntime& runtime,PPCContext& ctx) {
  Check(ctx.r3.u32==cookie,"guest startup cookie wrong");
  auto* thread=k::KernelThread::GetCallingThread();Check(thread && thread->GetPCRPtr()==ctx.r13.u32,"guest r13/PCR binding wrong");
  auto pcr=runtime.GetGuestMemory().Load<k::X_KPCR>(ctx.r13.u32);Ok(pcr,"PCR unreadable");
  Check(pcr->pcr_ptr==ctx.r13.u64,"PCR self address wrong");
  Check(pcr->stack_end_ptr<ctx.r1.u32 && ctx.r1.u32<pcr->stack_base_ptr && ctx.r1.u32%16==0,"guest stack bounds/alignment wrong");
  Check(!runtime.GetGuestMemory().GetReadOnlySpan(u32(pcr->stack_end_ptr)-1,1),"guest stack guard readable");
}
}

TEST_CASE("original kernel: guest context and object semantics survive repeated teardown", "[mw3][kernel]") {
  for(unsigned cycle=0;cycle<4;++cycle) {
    Fixture fixture(cycle);State state;
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
    Fixture fixture(cycle);State state;
    state.body=[&](PPCContext& ctx,u8* base) {
      Context(*fixture.runtime,ctx);state.armed.store(true,std::memory_order_release);
      Call(ctx,base,"ExTerminateThread",{42});state.returned.store(true,std::memory_order_release);
    };
    REQUIRE_NOTHROW(fixture.Run(state,false,true));REQUIRE_NOTHROW(fixture.Finish());
  }
}
