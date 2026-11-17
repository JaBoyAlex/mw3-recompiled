// SPDX-License-Identifier: GPL-3.0-only
// Test-only interposer for the pinned SDK ABI, never part of a game package.
#include <rex/memory/virtual_memory.h>
#include <dlfcn.h>
#include <atomic>
#include <cstdio>
#include <cstdlib>

namespace {
std::atomic<unsigned> count{0}, fired{0};
std::atomic<uintptr_t> first_base{0};
}
extern "C" uintptr_t MW3FaultBase() { return fired.load() ? first_base.load() : 0; }

namespace rex::memory {
void* MapFileView(FileMappingHandle handle,void* base,size_t length,PageAccess access,size_t offset) {
  using Function=void*(*)(FileMappingHandle,void*,size_t,PageAccess,size_t);
  // This spelling is verified against the exact pinned lib's exported symbol.
  static auto original=reinterpret_cast<Function>(dlsym(RTLD_NEXT,"_ZN3rex6memory11MapFileViewEiPvmNS0_10PageAccessEm"));
  if(!original) { std::fputs("FAULT_SHIM_ERROR:original symbol missing\n",stderr);std::_Exit(90); }
  const char* setting=std::getenv("MW3_FAIL_MAP_VIEW");
  if(setting && base) {
    const unsigned target=static_cast<unsigned>(std::strtoul(setting,nullptr,10));
    const unsigned index=++count;
    if(index == 1) first_base=reinterpret_cast<uintptr_t>(base);
    if(target >= 1 && target <= 8 && index == target) {
      ++fired;std::fprintf(stderr,"FAULT_INJECTION_TRIGGERED:%u\n",index);return nullptr;
    }
  }
  return original(handle,base,length,access,offset);
}
}
