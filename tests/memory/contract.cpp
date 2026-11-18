// SPDX-License-Identifier: GPL-3.0-only
// Original game-free contracts. Geometry is data, never guest instructions.
#include <rex/app/app.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/heap.h>
#include <rex/kernel/memory_view.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/types/thread.h>
#include <rex/ppc/image.h>
#include <rex/ppc/context.h>
#include <rex/ppc/recompiled_code.h>
#include <rex/memory/virtual_memory.h>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <semaphore>
#include <stdexcept>
#include <string>
#include <vector>

using namespace rex::kernel;
namespace {
void Require(bool condition,const char* reason) {
  if(!condition) throw std::runtime_error(reason);
}
template<class T> void Ok(const T& result,const char* reason) { Require(bool(result),reason); }
constexpr uint32_t callback_address=uint32_t(PPC_CODE_BASE)+0x1000;
GuestAddressSpace* address_space=nullptr;
uint32_t stack_low=0,stack_high=0,stack_pointer=0;
std::atomic<bool> captured{false};
std::binary_semaphore capture_ready{0},release_callback{0};
void Capture(PPCContext& context,uint8_t*) {
  auto* thread=KernelThread::GetCallingThread();
  if(!thread) return;
  address_space=thread->GetAddressSpace();
  auto pcr=thread->GetRuntime().GetGuestMemory().Load<X_KPCR>(thread->GetPCRPtr());
  if(!pcr) return;
  stack_low=pcr->stack_end_ptr;
  stack_high=pcr->stack_base_ptr;
  stack_pointer=context.r1.u32;
  captured.store(true,std::memory_order_release);
  capture_ready.release();
  release_callback.acquire();
}
const PPCFuncMapping mappings[]={{callback_address,&Capture},{0,nullptr}};
const rex::ppc::PPCImage image{PPC_CODE_BASE,PPC_CODE_SIZE,PPC_IMAGE_BASE,PPC_IMAGE_SIZE,mappings};
struct TestApp : rex::app::App { TestApp():App("mw3_memory_contract"){} };
struct StackFixture {
  TitleRuntime& runtime;
  uint32_t handle;
  ~StackFixture() {
    release_callback.release();
    uint64_t timeout=uint64_t(-int64_t{20000000});
    if(runtime.GetThreadRegistry().GetObjectWaiter().WaitGuestObject(handle,0,0,0,&timeout)!=0) {
      std::fputs("MEMORY_CONTRACT_FAIL:stack fixture shutdown timeout\n",stderr);
      std::fflush(stderr);std::_Exit(2);
    }
    CloseOwned(runtime.GetObjectTable(),handle);
  }
};
uint32_t Random(uint32_t& seed) { seed=seed*1664525u+1013904223u;return seed; }
uint32_t Allocate(GuestMemory& memory,uint32_t size=0x10000,uint32_t alignment=0x10000,GuestHeap heap=GuestHeap::kTitle) {
  auto result=memory.Allocate(size,alignment,GuestProtect::kReadWrite,heap);
  Ok(result,"allocation failed");Require(*result%alignment==0,"allocation alignment violated");return *result;
}
void Geometry(uint32_t at,uint32_t length) {
  const uint64_t end=uint64_t(at)+length;
  const uint64_t image_end=PPC_IMAGE_BASE+PPC_IMAGE_SIZE;
  const uint64_t table_end=image_end+PPC_CODE_SIZE*2;
  Require(end<=PPC_IMAGE_BASE || at>=image_end,"allocation overlaps executable image");
  Require(end<=image_end || at>=table_end,"allocation overlaps function table");
}
void Stack(GuestMemory& memory) {
  Require(stack_low>=KernelThread::kStackAddressRangeBegin && stack_high<=KernelThread::kStackAddressRangeEnd &&
          stack_low<stack_pointer && stack_pointer<stack_high && stack_pointer%16==0,"invalid runtime stack bounds");
  // Keep the runtime-created stack alive with a host semaphore. A completed
  // callback releases its stack even when its object handle remains open.
  Ok(memory.GetWritableSpan(stack_low,stack_high-stack_low),"stack is not writable");
  Require(!memory.GetReadOnlySpan(stack_low-1,1),"stack guard is readable");
  Require(!memory.GetWritableSpan(stack_low-1,2),"cross-guard write accepted");
  auto view=memory.GetView();
  Require(!view.TryLoad<uint32_t>(stack_low-2),"checked view crossed guard");
}
void Aliases(GuestMemory& memory,uint32_t seed) {
  const uint32_t at=Allocate(memory,0x10000,0x10000,GuestHeap::kPhysical);
  Require(at>=0xa0000000u && at<0xc0000000u,"wrong physical window");
  const uint32_t alias=at+0x20000000u;
  auto view=memory.GetView();
  for(unsigned i=0;i<512;++i) {
    const uint32_t offset=(Random(seed)%16384)*4,value=Random(seed);
    view.Store<uint32_t>(at+offset,value);
    Require(view.Load<uint32_t>(alias+offset)==value,"A/C alias mismatch");
    auto* physical=address_space->TranslatePhysical<const uint8_t*>(address_space->GetPhysicalAddress(at+offset));
    Require(physical[0]==uint8_t(value>>24) && physical[3]==uint8_t(value),"physical bytes/endian mismatch");
    view.Store<uint32_t>(alias+offset,~value);
    Require(view.Load<uint32_t>(at+offset)==~value,"C/A alias mismatch");
  }
  Ok(memory.Free(at),"physical release failed");
  Require(!memory.GetReadOnlySpan(at,4),"released physical mapping readable");
}
void Boundaries(GuestMemory& memory) {
  std::array<std::byte,8> bytes{};
  for(auto [address,length]:std::array<std::pair<uint32_t,uint32_t>,6>{{{0,1},{0xfffffffcu,8},{0xffffffffu,2},
      {0x7efffffcu,8},{0x7ffffffcu,8},{0xdead0000u,8}}}) {
    Require(!memory.GetReadOnlySpan(address,length),"invalid read range accepted");
    Require(!memory.GetWritableSpan(address,length),"invalid write range accepted");
  }
  Require(!memory.CopyFrom(0xfffffffcu,bytes),"wrapping copy accepted");
  Require(!memory.HostToGuest(bytes.data()),"foreign host pointer accepted");
  const uint32_t at=Allocate(memory,0x20000);
  Ok(memory.Store(at+0xffff, uint8_t{0x6a}),"boundary canary write failed");
  Ok(memory.Protect(at+0x10000,0x10000,GuestProtect::kReadOnly),"second-page protection failed");
  bytes.fill(std::byte{0xb7});
  Require(!memory.CopyTo(at+0xffff,bytes),"partly read-only copy accepted");
  auto unchanged=memory.Load<uint8_t>(at+0xffff);
  Ok(unchanged,"canary read failed");Require(*unchanged==0x6a,"failed write changed prefix");
  Require(!memory.GetView().TryStore<uint32_t>(at+0xfffe,0x12345678),"checked write crossed protection");
  Ok(memory.Free(at),"release failed");
  Require(!memory.GetReadOnlySpan(at,1),"released address accepted");
  Require(!memory.Free(at),"double free accepted");
}
void Reservation() {
  auto* heap=address_space->LookupHeap(0x10000000);
  Require(heap!=nullptr,"4KiB virtual heap missing");
  const uint32_t page=heap->GetPageSize(),rw=kMemoryProtectRead|kMemoryProtectWrite;
  uint32_t at=0;
  Require(heap->Alloc(page*3,page,kMemoryAllocationReserve,kMemoryProtectNoAccess,false,&at),"reserve failed");
  rex::kernel::MemoryView view(*address_space);
  Require(!view.TryLoad<uint32_t>(at),"uncommitted reservation readable");
  Require(heap->AllocFixed(at+page,page,page,kMemoryAllocationCommit,rw),"middle commit failed");
  Require(view.TryStore<uint32_t>(at+page,0x12345678),"committed write failed");
  Require(!view.TryLoad<uint32_t>(at+page-2),"read crossed uncommitted page");
  Require(!view.TryLoad<uint32_t>(at+page*2-2),"read crossed commit end");
  Require(heap->Protect(at+page,page,kMemoryProtectRead),"read-only change failed");
  Require(!view.TryStore<uint32_t>(at+page,0),"read-only write accepted");
  Require(view.TryLoad<uint32_t>(at+page)==0x12345678,"protection changed contents");
  Require(heap->Decommit(at+page,page),"decommit failed");
  Require(heap->AllocFixed(at+page,page,page,kMemoryAllocationCommit,rw),"recommit failed");
  Require(view.TryStore<uint32_t>(at+page,0x87654321),"recommitted write failed");
  Require(view.TryLoad<uint32_t>(at+page)==0x87654321,"recommitted value differs");
  Require(heap->Release(at),"reservation release failed");
  Require(!view.TryLoad<uint32_t>(at+page),"released reservation readable");
}
void Decommitted(GuestMemory& memory,const std::string& scenario) {
  const uint32_t at=Allocate(memory);
  auto* heap=address_space->LookupHeap(at);
  Require(heap->Decommit(at,0x10000),"decommit fixture failed");
  HeapAllocation info{};
  Require(heap->QueryRegionInfo(at,&info) && !(info.state&kMemoryAllocationCommit),"page state remained committed");
  if(scenario=="decommit-copy") Require(!memory.GetReadOnlySpan(at,4),"GuestMemory accepted decommitted page");
  else if(scenario=="decommit-store") Require(!memory.Store(at,uint32_t{0x12345678}),"GuestMemory wrote decommitted page");
  else Require(!memory.GetView().TryLoad<uint32_t>(at),"MemoryView accepted decommitted page");
  Ok(memory.Free(at),"decommitted release failed");
}
void Stress(GuestMemory& memory,uint32_t seed,bool mutate) {
  struct Block {uint32_t at,size,word;};
  std::vector<Block> blocks;
  auto check=[&](const Block& block) {
    auto first=memory.GetView().TryLoad<uint32_t>(block.at);
    auto last=memory.GetView().TryLoad<uint32_t>(block.at+block.size-4);
    Require(first && last && *first==(block.word^(mutate?1u:0u)) && *last==~block.word,"seeded oracle/content mismatch");
  };
  for(unsigned iteration=0;iteration<2048;++iteration) {
    if(!blocks.empty() && (blocks.size()>=32 || Random(seed)%3==0)) {
      const auto index=Random(seed)%blocks.size();check(blocks[index]);
      Ok(memory.Free(blocks[index].at),"stress release failed");
      blocks.erase(blocks.begin()+index);
    } else {
      const uint32_t size=(1+Random(seed)%2)*0x10000,alignment=0x10000u<<(Random(seed)%5);
      const uint32_t at=Allocate(memory,size,alignment),word=Random(seed);
      Geometry(at,size);
      for(const auto& block:blocks) Require(uint64_t(at)+size<=block.at || uint64_t(block.at)+block.size<=at,"live allocations overlap");
      memory.GetView().Store<uint32_t>(at,word);memory.GetView().Store<uint32_t>(at+size-4,~word);
      blocks.push_back({at,size,word});
    }
    for(const auto& block:blocks) check(block);
  }
  for(const auto& block:blocks) {check(block);Ok(memory.Free(block.at),"final release failed");}
  std::puts("MEMORY_STRESS_OPERATIONS:2048");
}
}

int main(int argc,char** argv) {
  if(argc<3) return 2;
  const std::string scenario=argv[1];const uint32_t seed=std::strtoul(argv[2],nullptr,0);
  TestApp app;
  if(!app.Init(rex::CLIArgList::Parse(argc-2,argv+2))) return 2;
  int result=0;
  try {
    TitleRuntime runtime(image);
    Ok(runtime.GetTitlePaths().entry.Set(""),"fixture entry setup failed");
    Ok(runtime.Load(),"synthetic runtime load failed");
    auto thread=std::make_unique<KernelThread>(runtime,512*1024,0,callback_address,0,0,true,false);
    auto launched=runtime.GetThreadRegistry().Launch(std::move(thread));Ok(launched,"stack fixture launch failed");
    {
    StackFixture fixture{runtime,*launched};
    Require(capture_ready.try_acquire_for(std::chrono::seconds(2)),"stack fixture capture timeout");
    Require(captured.load(std::memory_order_acquire) && address_space,"stack context not captured");
    auto& memory=runtime.GetGuestMemory();
    if(scenario=="stack") Stack(memory);
    else if(scenario=="aliases") Aliases(memory,seed);
    else if(scenario=="boundaries") Boundaries(memory);
    else if(scenario=="reservation") Reservation();
    else if(scenario=="decommit-copy" || scenario=="decommit-view" || scenario=="decommit-store") Decommitted(memory,scenario);
    else if(scenario=="release-policy") {
      const uint32_t at=Allocate(memory);Ok(memory.Free(at),"policy fixture free failed");
      Require(!memory.GetReadOnlySpan(at,1),"checked API accepted released page");
      size_t length=4096;rex::memory::PageAccess access{};
      Require(rex::memory::QueryProtect(runtime.GetMembase().TranslateVirtual(at),length,access),"host policy query failed");
      std::printf("MEMORY_RELEASE_DEFAULT_HOST_ACCESS:%u\n",unsigned(access));
    }
    else if(scenario=="stress" || scenario=="bad-oracle") Stress(memory,seed,scenario=="bad-oracle");
    else if(scenario=="guard-read" || scenario=="readonly-write" || scenario=="released-read" || scenario=="decommitted-read") {
      uint32_t at=stack_low-1;
      if(scenario!="guard-read") {
        at=Allocate(memory);
        if(scenario=="released-read") Ok(memory.Free(at),"fault fixture release failed");
        else if(scenario=="decommitted-read") Require(address_space->LookupHeap(at)->Decommit(at,0x10000),"fault fixture decommit failed");
        else Ok(memory.Protect(at,0x10000,GuestProtect::kReadOnly),"fault fixture protect failed");
      }
      auto* pointer=runtime.GetMembase().TranslateVirtual<volatile uint8_t*>(at);
      std::fprintf(stderr,"MEMORY_FAULT_ARMED:%s guest=%08x host=%p\n",scenario.c_str(),at,const_cast<uint8_t*>(pointer));
      std::fflush(stderr);
      if(scenario=="readonly-write") *pointer=0x55;
      else {volatile uint8_t value=*pointer;(void)value;}
      throw std::runtime_error("forbidden raw access did not fault");
    } else throw std::runtime_error("unknown scenario");
    }
    runtime.Unload();
    Require(!runtime.IsLoaded(),"synthetic runtime remained loaded");
    std::puts("MEMORY_CONTRACT_PASS");
  } catch(const std::exception& error) {
    std::fprintf(stderr,"MEMORY_CONTRACT_FAIL:%s\n",error.what());result=1;
  }
  app.Shutdown();return result;
}
