// SPDX-License-Identifier: GPL-3.0-only
#include <ppc_recomp_shared.h>
#include "guest_memory.h"
#include "guest.h"
#include "kernel/kernel.h"
#include "kernel/objects.h"
#include "crash.h"
#include "common.h"

PPC_EXTERN_FUNC(__imp__ExCreateThread);
PPC_EXTERN_FUNC(__imp__NtResumeThread);
PPC_EXTERN_FUNC(__imp__ExTerminateThread);
PPC_EXTERN_FUNC(__imp__NtClose);
inline bool terminate_body = false;
inline std::atomic<unsigned> diagnostic_threads{0};

// Only native diagnostic registration is adapted; no guest service is stubbed.
void crash::RegisterThread(const char*) { ++diagnostic_threads; }
void crash::UnregisterThread() { --diagnostic_threads; }

void Callback(PPCContext& ctx, uint8_t* base) {
  ObserveContext(ctx);
  if (terminate_body) {
    ctx.r3.u32 = 42;
    __imp__ExTerminateThread(ctx, base);
    ++after_terminate;
  }
}

struct MW2Backend {
  uint32_t Allocate(uint32_t size) { return kernel::AllocateGuest(size, 4096); }
  uint32_t Physical(uint32_t size) { return kernel::AllocatePhysical(size, 4096); }
  uint8_t* Raw(uint32_t at) { return guest::Base() + at; }
  uint32_t Load(uint32_t at) { return *GuestPtr<be32>(at); }
  void Store(uint32_t at, uint32_t value) { *GuestPtr<be32>(at) = value; }
  uint64_t TableBegin() { return PPC_IMAGE_BASE + PPC_IMAGE_SIZE; }
  uint64_t TableEnd() { return TableBegin() + PPC_CODE_SIZE * 2; }
  uint32_t Spawn(bool terminate, bool suspended) {
    terminate_body = terminate;
    auto* cell = reinterpret_cast<PPCFunc**>(guest::Base() + TableBegin() + (uint64_t(kCallback-PPC_CODE_BASE)*2));
    *cell = &Callback;
    const uint32_t out = Allocate(4096);
    PPCContext ctx{};
    ctx.r3.u32=out; ctx.r4.u32=512*1024; ctx.r7.u32=kCallback;
    ctx.r8.u32=kCookie; ctx.r9.u32=suspended ? 1 : 0;
    __imp__ExCreateThread(ctx, guest::Base());
    Require(ctx.r3.u32 == 0, "ExCreateThread returned failure");
    return Load(out);
  }
  bool Wait(uint32_t handle, unsigned ms) {
    auto object = kernel::LookupHandle(handle);
    auto dispatcher = std::dynamic_pointer_cast<kernel::Dispatcher>(object);
    Require(bool(dispatcher), "thread handle is not a dispatcher");
    kernel::Dispatcher* pointer = dispatcher.get();
    int64_t timeout = -int64_t(ms)*10000;
    return kernel::Wait(&pointer, 1, false, &timeout) == 0;
  }
  void Resume(uint32_t handle) {
    PPCContext ctx{}; ctx.r3.u32=handle;
    __imp__NtResumeThread(ctx,guest::Base());
    Require(ctx.r3.u32 == 0, "resume failed");
  }
  void Close(uint32_t handle) {
    PPCContext ctx{}; ctx.r3.u32=handle;
    __imp__NtClose(ctx,guest::Base());
  }
};

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  std::unique_ptr<HostCanary> canary;
  try {
    if(std::string(argv[1]) == "host-range-collision") {
      canary=std::make_unique<HostCanary>();host_canary=canary.get();
    }
  } catch(const std::exception& e) {
    std::fprintf(stderr,"SETUP_ERROR:%s\n",e.what());return 2;
  }
  if(!guest::Initialise()) return 2;
  if(canary) canary->MarkRuntimeRange(reinterpret_cast<uintptr_t>(guest::Base()),0x100000000ull);
  MW2Backend backend;
  const int result = RunContract(backend, argv[1]);
  const auto deadline = std::chrono::steady_clock::now()+std::chrono::seconds(2);
  while(diagnostic_threads.load() && std::chrono::steady_clock::now()<deadline)
    std::this_thread::yield();
  return result;
}
