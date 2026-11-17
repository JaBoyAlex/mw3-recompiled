// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic service contract; contains no translated game instructions.
#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <memory>
#include <sys/mman.h>

inline constexpr uint32_t kCallback = uint32_t(PPC_CODE_BASE) + 0x1000;
inline constexpr uint32_t kCookie = 0x9abcdef0;
inline std::atomic<unsigned> started{0}, after_terminate{0};
inline std::atomic<bool> callback_ok{true};

// Own one host page where the baseline ReXGlue probes its first mapping. No
// existing mapping is replaced by this fixture. The runtime must preserve it.
struct HostCanary {
  static constexpr uintptr_t kAddress = 0x130001000ull;
  uint8_t* page = nullptr;
  bool still_owned = true;
  HostCanary() {
    void* got = mmap(reinterpret_cast<void*>(kAddress),4096,PROT_READ|PROT_WRITE,
                     MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    if(got == MAP_FAILED) throw std::runtime_error("host-canary address unavailable");
    if(got != reinterpret_cast<void*>(kAddress)) {
      munmap(got,4096);throw std::runtime_error("kernel ignored exact no-replace mapping");
    }
    page = static_cast<uint8_t*>(got);
    std::memset(page,0xa7,4096);
  }
  bool Intact() const {
    for(unsigned i=0;i<4096;++i) if(page[i] != 0xa7) return false;
    return true;
  }
  void MarkRuntimeRange(uintptr_t begin,uint64_t length) {
    if(kAddress >= begin && kAddress-begin < length) still_owned=false;
  }
  ~HostCanary() { if(page && still_owned) munmap(page,4096); }
};
inline HostCanary* host_canary = nullptr;

inline void Require(bool condition, const char* reason) {
  if (!condition) throw std::runtime_error(reason);
}

// Real backend callbacks inspect the runtime-created register context, then
// either return or invoke the backend's actual ExTerminateThread service.
template<class Context>
void ObserveContext(Context& ctx) {
  const bool valid = ctx.r3.u32 == kCookie && ctx.r13.u32 != 0 &&
                     ctx.r1.u32 != 0 && (ctx.r1.u32 & 15) == 0;
  if (!valid) callback_ok.store(false);
  started.fetch_add(1);
}

template<class Backend>
void MemoryContract(Backend& backend) {
  const uint32_t physical = backend.Physical(4096);
  Require(physical >= 0xA0000000 && physical < 0xC0000000, "physical allocation outside expected aperture");
  const uint32_t alias = physical + 0x20000000;
  uint32_t seed = 0x12345678;
  for (unsigned i=0; i<1024; ++i) {
    seed = seed * 1664525u + 1013904223u;
    backend.Store(physical + i*4, seed);
    Require(backend.Load(alias + i*4) == seed, "A-to-C alias incoherent");
    backend.Store(alias + i*4, ~seed);
    Require(backend.Load(physical + i*4) == ~seed, "C-to-A alias incoherent");
  }
  const uint32_t allocated = backend.Allocate(4096);
  Require(allocated != 0 && allocated % 4096 == 0, "unaligned/failed virtual allocation");
  const uint64_t begin = backend.TableBegin(), end = backend.TableEnd();
  std::printf("{\"allocation\":%u,\"table_begin\":%llu,\"table_end\":%llu}\n",
              allocated, static_cast<unsigned long long>(begin), static_cast<unsigned long long>(end));
  Require(uint64_t(allocated) + 4096 <= begin || allocated >= end, "virtual allocation overlaps function table");
  backend.Store(allocated, 0x12345678);
  Require(backend.Load(allocated) == 0x12345678, "guest endian value does not round trip");
  const auto* bytes = backend.Raw(allocated);
  Require(bytes[0] == 0x12 && bytes[1] == 0x34 && bytes[2] == 0x56 && bytes[3] == 0x78,
          "guest word is not big endian");
}

template<class Backend>
void ThreadContract(Backend& backend, bool terminate, bool suspended) {
  started = 0; after_terminate = 0; callback_ok = true;
  const uint32_t handle = backend.Spawn(terminate, suspended);
  Require(handle != 0, "thread creation failed");
  if (suspended) {
    Require(!backend.Wait(handle, 20), "suspended thread unexpectedly completed");
    Require(started.load() == 0, "suspended thread entered before resume");
    backend.Resume(handle);
  }
  Require(backend.Wait(handle, 2000), "guest thread did not finish before deadline");
  Require(started.load() == 1 && callback_ok.load(), "guest thread context/cookie incorrect");
  backend.Close(handle);
  Require(!terminate || after_terminate.load() == 0, "ExTerminateThread returned to guest callback");
}

template<class Backend>
int RunContract(Backend& backend, const std::string& scenario) {
  try {
    if (scenario == "host-range-collision")
      Require(host_canary && host_canary->Intact(), "runtime replaced an occupied host mapping");
    else if (scenario == "memory") MemoryContract(backend);
    else if (scenario == "thread-return") ThreadContract(backend, false, false);
    else if (scenario == "thread-suspended") ThreadContract(backend, false, true);
    else if (scenario == "thread-terminate") ThreadContract(backend, true, false);
    else throw std::runtime_error("unknown scenario");
    std::puts("CONFORMANCE_PASS");
    return 0;
  } catch (const std::exception& e) {
    std::fprintf(stderr, "CONFORMANCE_FAIL:%s\n", e.what());
    return 1;
  }
}
