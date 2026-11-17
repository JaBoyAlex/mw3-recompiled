// SPDX-License-Identifier: GPL-3.0-only
#include <rex/app/app.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/object/object_table.h>
#include <rex/ppc/image.h>
#include <rex/ppc/context.h>
#include <rex/ppc/recompiled_code.h>
#include <rex/memory/mapped_ptr.h>
#include <dlfcn.h>
#include "common.h"

REX_EXTERN(__imp__ExTerminateThread);
inline bool terminate_body = false;
void Callback(PPCContext& ctx, uint8_t* base) {
  ObserveContext(ctx);
  if(terminate_body) {
    ctx.r3.u32=42;
    __imp__ExTerminateThread(ctx,base);
    ++after_terminate;
  }
}

const PPCFuncMapping mappings[]={{kCallback,&Callback},{0,nullptr}};
const rex::ppc::PPCImage image{PPC_CODE_BASE,PPC_CODE_SIZE,PPC_IMAGE_BASE,PPC_IMAGE_SIZE,mappings};

struct ReXBackend {
  rex::kernel::TitleRuntime& runtime;
  uint32_t Allocate(uint32_t size) {
    auto r=runtime.GetGuestMemory().Allocate(size,4096,rex::kernel::GuestProtect::kReadWrite);
    Require(bool(r), "virtual allocation failed"); return *r;
  }
  uint32_t Physical(uint32_t size) {
    auto r=runtime.GetGuestMemory().Allocate(size,65536,rex::kernel::GuestProtect::kReadWrite,rex::kernel::GuestHeap::kPhysical);
    Require(bool(r), "physical allocation failed"); return *r;
  }
  uint8_t* Raw(uint32_t at) { return runtime.GetMembase().TranslateVirtual(at); }
  uint32_t Load(uint32_t at) { return *reinterpret_cast<rex::be_u32*>(Raw(at)); }
  void Store(uint32_t at,uint32_t value) { *reinterpret_cast<rex::be_u32*>(Raw(at))=value; }
  uint64_t TableBegin() { return PPC_IMAGE_BASE + PPC_IMAGE_SIZE; }
  uint64_t TableEnd() { return TableBegin() + PPC_CODE_SIZE*2; }
  uint32_t Spawn(bool terminate,bool suspended) {
    terminate_body=terminate;
    auto thread=std::make_unique<rex::kernel::KernelThread>(runtime,512*1024,0,kCallback,kCookie,suspended?1:0,true,false);
    auto launched=runtime.GetThreadRegistry().Launch(std::move(thread));
    Require(bool(launched),"guest thread creation failed"); return *launched;
  }
  bool Wait(uint32_t handle,unsigned ms) {
    uint64_t timeout=static_cast<uint64_t>(-int64_t(ms)*10000);
    return runtime.GetThreadRegistry().GetObjectWaiter().WaitGuestObject(handle,0,0,0,&timeout)==0;
  }
  void Resume(uint32_t handle) {
    auto thread=runtime.GetThreadRegistry().FindByHandle(handle);
    Require(bool(thread),"missing thread");thread->Resume();
  }
  void Close(uint32_t handle) { rex::kernel::CloseOwned(runtime.GetObjectTable(),handle); }
};

struct ProbeApp : rex::app::App {
  ProbeApp():App("mw3_synthetic_conformance"){}
};

int main(int argc,char** argv) {
  if(argc<2) return 2;
  const std::string scenario=argv[1];
  std::unique_ptr<HostCanary> canary;
  try {
    if(scenario == "host-range-collision") {
      canary=std::make_unique<HostCanary>();host_canary=canary.get();
    }
  } catch(const std::exception& e) {
    std::fprintf(stderr,"SETUP_ERROR:%s\n",e.what());return 2;
  }
  ProbeApp app;
  if(!app.Init(rex::CLIArgList::Parse(argc-1,argv+1))) return 2;
  rex::kernel::TitleRuntime runtime(image);
  auto cleared=runtime.GetTitlePaths().entry.Set("");
  if(!cleared) return 2;
  if(auto loaded=runtime.Load(); !loaded) {
    std::fprintf(stderr,"LOAD_FAIL:%s\n",loaded.error().message.c_str());return 2;
  }
  if(canary) canary->MarkRuntimeRange(reinterpret_cast<uintptr_t>(runtime.GetMembase().GetBase()),0x120000000ull);
  ReXBackend backend{runtime};
  int result=0;
  if(scenario == "reload-lifecycle") {
    try {
      for(unsigned cycle=0;cycle<16;++cycle) {
        MemoryContract(backend);
        ThreadContract(backend,false,false);
        ThreadContract(backend,false,true);
        ThreadContract(backend,true,false);
        runtime.Unload();
        Require(!runtime.IsLoaded(),"runtime remained loaded after unload");
        if(cycle != 15) {
          auto reloaded=runtime.Load();
          Require(bool(reloaded),"runtime reload failed");
        }
      }
      std::puts("LIFECYCLE_CYCLES:16");
      std::puts("CONFORMANCE_PASS");
    } catch(const std::exception& e) {
      std::fprintf(stderr,"CONFORMANCE_FAIL:%s\n",e.what());result=1;
    }
  } else if(scenario == "mapping-failure-cleanup") {
    try {
      auto failed_base=reinterpret_cast<uintptr_t(*)()>(dlsym(RTLD_DEFAULT,"MW3FaultBase"));
      Require(failed_base && failed_base(),"mapping fault was not injected");
      const uintptr_t failed=failed_base(), active=reinterpret_cast<uintptr_t>(runtime.GetMembase().GetBase());
      Require(failed != active,"runtime reused a failed host range without retry");
      const uintptr_t end=failed+0x120000000ull;
      // Later power-of-two candidates can overlap the old range's tail. Probe
      // only the released portion outside the current runtime's owned span.
      const uintptr_t released_end=active > failed ? std::min(end,active) : end;
      const uintptr_t released_begin=active > failed ? failed : std::max(failed,active+uintptr_t{0x120000000ull});
      Require(released_end > released_begin,"no disjoint released span to verify");
      void* probe=mmap(reinterpret_cast<void*>(released_begin),released_end-released_begin,PROT_NONE,
                       MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
      Require(probe != MAP_FAILED,"failed mapping left an occupied reservation");
      if(probe != reinterpret_cast<void*>(released_begin)) {
        munmap(probe,released_end-released_begin);throw std::runtime_error("kernel ignored exact no-replace probe");
      }
      munmap(probe,released_end-released_begin);
      std::puts("CONFORMANCE_PASS");
    } catch(const std::exception& e) {
      std::fprintf(stderr,"CONFORMANCE_FAIL:%s\n",e.what());result=1;
    }
  } else result=RunContract(backend,scenario);
  runtime.Unload();
  app.Shutdown();
  return result;
}
