// SPDX-License-Identifier: GPL-3.0-only
// Original guarded research harness. No generated game instructions here.
#include MW3_GENERATED_INIT
#include MW3_DATA_IMPORT_HEADER
#include "mw3/xex.hpp"
#include <rex/app/title_app.h>
#include <rex/kernel/module.h>
#include <rex/kernel/object/module_object.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/types/xex.h>
#include <atomic>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <dlfcn.h>

bool VerifyProbeImportStops(rex::kernel::TitleRuntime&);
namespace {
rex::kernel::TitleRuntime* current = nullptr;
std::vector<std::byte> raw_header;
std::uint32_t header_address = 0, module_address = 0, cell_address = 0;
std::atomic<unsigned> queries{0};
using Function = void(*)(PPCContext&, u8*);
Function original_header_query = nullptr;

[[noreturn]] void Reject(const char* reason) {
  std::fprintf(stderr,"MW3_HEADER_GUARD_FAILED:%s\n",reason);
  std::fflush(stderr); std::_Exit(87);
}
void Require(bool ok, const char* reason) { if(!ok) Reject(reason); }
std::uint32_t LoadWord(std::uint32_t address) {
  auto value = current->GetGuestMemory().Load<rex::be_u32>(address);
  Require(bool(value),"unreadable guest word"); return *value;
}
void VerifyHeader() {
  auto bytes = current->GetGuestMemory().GetReadOnlySpan(header_address,static_cast<u32>(raw_header.size()));
  Require(bool(bytes),"unreadable guest header");
  Require(std::memcmp(bytes->data(),raw_header.data(),raw_header.size())==0,"guest header differs from owned raw header");
  Require(LoadWord(MW3_MODULE_HANDLE_IMPORT)==cell_address,"module import cell binding changed");
  Require(LoadWord(cell_address)==module_address,"executable module handle changed");
  Require(LoadWord(module_address+offsetof(rex::kernel::X_LDR_DATA_TABLE_ENTRY,xex_header_base))==header_address,
          "module header pointer changed");
}
}

extern "C" void __imp__RtlImageXexHeaderField(PPCContext& ctx, u8* base) {
  try {
    Require(current && original_header_query,"header service not initialized");
    Require(++queries <= 16,"header query budget exceeded");
    const u32 pointer=ctx.r3.u32, key=ctx.r4.u32;
    if(std::getenv("MW3_HEADER_TEST_BAD_POINTER")) Require(false,"deliberate pointer rejection");
    Require(pointer==header_address,"unexpected header pointer");
    VerifyHeader();
    const u32 predicted=mw3::resolve_xex_optional_header(raw_header,pointer,key).value_or(0);
    original_header_query(ctx,base);
    Require(ctx.r3.u32==predicted,"SDK header result differs from independent oracle");
    VerifyHeader();
    std::fprintf(stderr,"MW3_HEADER_QUERY_PASS:pointer=%08x key=%08x result=%08x lr=%llx\n",
                 pointer,key,predicted,static_cast<unsigned long long>(ctx.lr));
    std::fflush(stderr);
  } catch(const std::exception&) { Reject("bounded header oracle rejected input"); }
}

class HeaderProbe final : public rex::app::TitleApp {
 public:
  HeaderProbe():TitleApp("mw3_private_header_probe",kPPCImageConfig){}
 protected:
  rex::AppSysRequirements GetRequirements() const override { return {}; }
  rex::Result<void> OnTitleLaunch(rex::kernel::TitleRuntime& runtime) override {
    current=&runtime;
    Require(!std::getenv("MW3_HEADER_TEST_BAD_BINDING") && VerifyProbeImportStops(runtime),"function binding verification");
    const char* path=std::getenv("MW3_HEADER_OWNED_FILE");
    Require(path!=nullptr,"owned header input missing");
    std::ifstream stream(path,std::ios::binary);
    Require(bool(stream),"owned header open failed");
    std::array<unsigned char,24> prefix{};
    stream.read(reinterpret_cast<char*>(prefix.data()),prefix.size());
    Require(bool(stream),"truncated owned header prefix");
    const u32 size=(u32(prefix[8])<<24)|(u32(prefix[9])<<16)|(u32(prefix[10])<<8)|prefix[11];
    Require(size>=24 && size<=mw3::max_xex_metadata,"owned header size bound");
    raw_header.resize(size); stream.seekg(0);
    stream.read(reinterpret_cast<char*>(raw_header.data()),size);
    Require(bool(stream),"truncated owned raw header");
    const auto handle=runtime.GetModuleRegistry().GetExecutable();
    Require(bool(handle),"missing executable module");
    auto module=runtime.GetObjectTable().Get<rex::kernel::ModuleObject>(*handle);
    Require(bool(module),"missing executable module object");
    header_address=module->user.guest_xex_header;
    module_address=module->hmodule_ptr;
    Require(header_address && module_address,"module/header pointer missing");
    Require(u64(module_address)+sizeof(rex::kernel::X_LDR_DATA_TABLE_ENTRY)<=0x100000000ull,"module pointer wraps");
    cell_address=LoadWord(MW3_MODULE_HANDLE_IMPORT);
    auto kernel_handle=runtime.GetModuleRegistry().FindKernelModule("xboxkrnl.exe");
    Require(bool(kernel_handle),"kernel module missing");
    auto kernel=runtime.GetObjectTable().Get<rex::kernel::ModuleObject>(*kernel_handle);
    Require(bool(kernel) && kernel->GetVariable(0x0193)==cell_address,"module-handle export mismatch");
    VerifyHeader();
    void* library=dlopen("librexkernel.so",RTLD_NOW|RTLD_NOLOAD);
    Require(library!=nullptr,"SDK kernel not loaded");
    original_header_query=reinterpret_cast<Function>(dlsym(library,"__imp__RtlImageXexHeaderField"));
    Require(original_header_query && original_header_query!=&__imp__RtlImageXexHeaderField,"SDK header provider missing/interposed");
    std::fprintf(stderr,"MW3_MODULE_HEADER_AUDIT_PASS:cell=%08x module=%08x header=%08x bytes=%u\n",
                 cell_address,module_address,header_address,size);
    std::fputs("MW3_PROBE_IMAGE_LOADED; only header query admitted\n",stderr);
    std::fflush(stderr);
    return rex::Ok();
  }
};
REX_TITLE_APP(HeaderProbe)
