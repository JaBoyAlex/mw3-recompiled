// SPDX-License-Identifier: GPL-3.0-only
// Maintained host diagnostics. Private generated guest sources are separate inputs.
#include MW3_GENERATED_INIT
#include MW3_DATA_IMPORT_HEADER
#include "mw3/xex.hpp"
#include <rex/app/app.h>
#include <rex/kernel/module.h>
#include <rex/kernel/object/module_object.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/types/thread.h>
#include <rex/kernel/types/xex.h>
#include <rex/platform/dynlib.h>
#include <rex/platform/sync.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#if REX_PLATFORM_WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

bool VerifyProbeImportStops(rex::kernel::TitleRuntime&);
extern "C" void __imp__RtlImageXexHeaderField(PPCContext&, u8*);
namespace k = rex::kernel;
namespace p = rex::platform;
namespace {
struct HostFailure : std::runtime_error { using std::runtime_error::runtime_error; };
k::TitleRuntime* current = nullptr;
k::ObjectPin stopped_object;
std::vector<std::byte> raw_header;
u32 header_address = 0, module_address = 0, cell_address = 0, thread_address = 0;
std::atomic<unsigned> queries = 0;
std::atomic<u32> thread_handle = 0;
std::string mode;
const char* diagnostic = nullptr;
unsigned diagnostic_code = 0;
thread_local bool guest_callback = false;
std::unique_ptr<p::Event> checkpoint, never, exited;
using Function = void (*)(PPCContext&, u8*);
Function original_header_query = nullptr;
p::DynamicLibrary kernel_library;

void PinCallingThread() {
  auto* thread = k::KernelThread::GetCallingThread();
  thread_handle.store(thread->GetHandle(), std::memory_order_release);
  thread_address = thread->GetGuestObject();
  if (!stopped_object) stopped_object = current->GetObjectTable().GetByAddress(thread_address);
}

[[noreturn]] void Reject(const char* reason) {
  std::fprintf(stderr, "MW3_LIFECYCLE_REJECT:%s\n", reason);
  diagnostic = reason;
  diagnostic_code = 87;
  if (guest_callback) {
    PinCallingThread();
    throw rex::ThreadStop{87};
  }
  throw HostFailure(reason);
}
void Require(bool ok, const char* reason) { if (!ok) Reject(reason); }
u32 LoadWord(u32 address) {
  auto value = current->GetGuestMemory().Load<rex::be_u32>(address);
  Require(bool(value), "unreadable guest word");
  return *value;
}
void VerifyHeader() {
  auto bytes = current->GetGuestMemory().GetReadOnlySpan(header_address, static_cast<u32>(raw_header.size()));
  Require(bool(bytes), "unreadable guest header");
  Require(std::memcmp(bytes->data(), raw_header.data(), raw_header.size()) == 0, "guest header differs from owned raw header");
  Require(LoadWord(MW3_MODULE_HANDLE_IMPORT) == cell_address, "module import cell binding changed");
  Require(LoadWord(cell_address) == module_address, "executable module handle changed");
  Require(LoadWord(module_address + offsetof(k::X_LDR_DATA_TABLE_ENTRY, xex_header_base)) == header_address,
          "module header pointer changed");
}
void PrepareAudit() {
  Require(VerifyProbeImportStops(*current), "function binding verification");
  const char* path = std::getenv("MW3_HEADER_OWNED_FILE");
  Require(path != nullptr, "owned header input missing");
  std::ifstream stream(path, std::ios::binary);
  Require(bool(stream), "owned header open failed");
  std::array<unsigned char, 24> prefix{};
  stream.read(reinterpret_cast<char*>(prefix.data()), prefix.size());
  Require(bool(stream), "truncated owned header prefix");
  const u32 size = (u32(prefix[8]) << 24) | (u32(prefix[9]) << 16) | (u32(prefix[10]) << 8) | prefix[11];
  Require(size >= 24 && size <= mw3::max_xex_metadata, "owned header size bound");
  raw_header.resize(size);
  stream.seekg(0);
  stream.read(reinterpret_cast<char*>(raw_header.data()), size);
  Require(bool(stream), "truncated owned raw header");
  auto handle = current->GetModuleRegistry().GetExecutable();
  Require(bool(handle), "missing executable module");
  auto module = current->GetObjectTable().Get<k::ModuleObject>(*handle);
  Require(bool(module), "missing executable module object");
  header_address = module->user.guest_xex_header;
  module_address = module->hmodule_ptr;
  Require(header_address && module_address, "module/header pointer missing");
  Require(u64(module_address) + sizeof(k::X_LDR_DATA_TABLE_ENTRY) <= 0x100000000ull, "module pointer wraps");
  cell_address = LoadWord(MW3_MODULE_HANDLE_IMPORT);
  auto kernel_handle = current->GetModuleRegistry().FindKernelModule("xboxkrnl.exe");
  Require(bool(kernel_handle), "kernel module missing");
  auto kernel = current->GetObjectTable().Get<k::ModuleObject>(*kernel_handle);
  Require(bool(kernel) && kernel->GetVariable(0x0193) == cell_address, "module-handle export mismatch");
  VerifyHeader();
  Require(kernel_library.LoadNamed("rexkernel", p::SymbolResolution::kImmediate), "SDK kernel provider unavailable");
  original_header_query = kernel_library.GetSymbol<Function>("__imp__RtlImageXexHeaderField");
  Require(original_header_query && original_header_query != &__imp__RtlImageXexHeaderField,
          "SDK header provider missing/interposed");
  std::fprintf(stderr, "MW3_MODULE_HEADER_AUDIT_PASS:cell=%08x module=%08x header=%08x bytes=%u\n",
               cell_address, module_address, header_address, size);
}

bool ReservationReleased(void* address) {
  if (!address) return false;
  constexpr std::size_t span = 0x120000000ull;
#if REX_PLATFORM_WIN32
  void* claimed = VirtualAlloc(address, span, MEM_RESERVE, PAGE_NOACCESS);
  if (!claimed) return false;
  const bool exact = claimed == address;
  return VirtualFree(claimed, 0, MEM_RELEASE) && exact;
#else
  void* claimed = mmap(address, span, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
  if (claimed == MAP_FAILED) return false;
  const bool exact = claimed == address;
  return munmap(claimed, span) == 0 && exact;
#endif
}
}

extern "C" [[noreturn]] void StopUnreviewedImport(const char* name, PPCContext& ctx) {
  guest_callback = true;
  PinCallingThread();
  diagnostic = name;
  diagnostic_code = 86;
  std::fprintf(stderr, "MW3_PROBE_UNREVIEWED_IMPORT:%s lr=%llx\n", name, static_cast<unsigned long long>(ctx.lr));
  std::fflush(stderr);
  throw rex::ThreadStop{86};
}

extern "C" void __imp__RtlImageXexHeaderField(PPCContext& ctx, u8* base) {
  struct GuestScope { GuestScope() { guest_callback = true; } ~GuestScope() { guest_callback = false; } } scope;
  PinCallingThread();
  Require(current && original_header_query, "header service not initialized");
  const auto number = ++queries;
  Require(number <= 16, "header query budget exceeded");
  if (mode == "bad-pointer") ctx.r3.u32 ^= 4;
  const u32 pointer = ctx.r3.u32, key = ctx.r4.u32;
  Require(pointer == header_address, "unexpected header pointer");
  VerifyHeader();
  if (number == 1) {
    for (u32 audit_key : {0x10100u, 0x10201u, 0x40006u, 0x103ffu}) {
      auto expected = mw3::resolve_xex_optional_header(raw_header, pointer, audit_key);
      Require(expected.has_value() && *expected != 0, "present-field audit fixture absent");
      PPCContext audit = ctx;
      audit.r3.u32 = pointer;
      audit.r4.u32 = audit_key;
      original_header_query(audit, base);
      Require(audit.r3.u32 == *expected, "present-field SDK/oracle disagreement");
      VerifyHeader();
      std::fprintf(stderr, "MW3_HEADER_ORACLE_CASE_PASS:key=%08x result=%08x\n", audit_key, *expected);
    }
  }
  auto predicted = mw3::resolve_xex_optional_header(raw_header, pointer, key).value_or(0);
  if (mode == "bad-oracle") predicted ^= 1;
  original_header_query(ctx, base);
  Require(ctx.r3.u32 == predicted, "SDK header result differs from independent oracle");
  VerifyHeader();
  std::fprintf(stderr, "MW3_HEADER_QUERY_PASS:pointer=%08x key=%08x result=%08x lr=%llx\n",
               pointer, key, predicted, static_cast<unsigned long long>(ctx.lr));
  if (mode == "interrupt") {
    checkpoint->Set();
    current->GetThreadRegistry().GetObjectWaiter().WaitHostObject(never.get(), std::chrono::seconds(5));
    Reject("interrupted guest wait unexpectedly returned");
  }
}

class LifecycleApp final : public rex::app::App {
 public:
  LifecycleApp() : App("mw3_private_lifecycle") {}
 protected:
  rex::AppSysRequirements GetRequirements() const override { return {}; }
};

int RunLifecycle(LifecycleApp& app, const rex::CLIArgList& args) {
  const char* selected = std::getenv("MW3_LIFECYCLE_CASE");
  mode = selected ? selected : "positive";
  const auto threads_before = p::detail::GetThreadCount();
  if (!app.Init(args)) return 90;
  std::unique_ptr<k::TitleRuntime> runtime = std::make_unique<k::TitleRuntime>(kPPCImageConfig);
  int result = 90;
  void* reservation = nullptr;
  try {
    checkpoint = p::Event::CreateManualResetEvent(false);
    never = p::Event::CreateManualResetEvent(false);
    exited = p::Event::CreateManualResetEvent(false);
    Require(checkpoint && never && exited, "host event allocation failed");
    current = runtime.get();
    Require(bool(runtime->Load()), "title load failed");
    reservation = runtime->GetMembase().GetBase();
    PrepareAudit();
    auto exit_guard = runtime->OnTitleExit([](k::TitleExitReason) { exited->Set(); });
    Require(bool(runtime->Launch()), "title launch failed");
    if (mode == "interrupt") {
      Require(p::Wait(checkpoint.get(), false, std::chrono::seconds(5)) == p::WaitResult::kSuccess,
              "interrupt checkpoint deadline");
      auto pin = runtime->GetThreadRegistry().FindByHandle(thread_handle.load(std::memory_order_acquire));
      Require(bool(pin), "interrupt target missing");
      std::fputs("MW3_LIFECYCLE_INTERRUPT_REQUESTED:exit=88\n", stderr);
      pin->RequestStop(88);
      diagnostic_code = 88;
    }
    Require(p::Wait(exited.get(), false, std::chrono::seconds(8)) == p::WaitResult::kSuccess,
            "title exit deadline");
    auto object = runtime->GetGuestMemory().Load<k::X_KTHREAD>(thread_address);
    Require(stopped_object && object && object->terminated == 1, "stopped thread metadata missing");
    Require(object->exit_status == diagnostic_code, "diagnostic exit code lost");
    if (mode == "positive") Require(diagnostic && std::strcmp(diagnostic, "NtAllocateVirtualMemory") == 0,
                                    "unexpected startup boundary");
    result = static_cast<int>(diagnostic_code);
    std::fprintf(stderr, "MW3_LIFECYCLE_THREAD_STOPPED:exit=%d queries=%u\n", result, queries.load());
  } catch (const HostFailure&) {
    result = 87;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "MW3_LIFECYCLE_ERROR:%s\n", error.what());
  }
  stopped_object = {};
  kernel_library.Close();
  original_header_query = nullptr;
  runtime->Unload();
  if (runtime->IsLoaded() || k::GetProcessRuntime() != nullptr) result = 90;
  runtime.reset();
  current = nullptr;
  const bool released = ReservationReleased(reservation);
  std::fprintf(stderr, "MW3_LIFECYCLE_UNLOADED:reservation_released=%u\n", unsigned(released));
  if (released) std::fputs("MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208\n", stderr);
  if (!released) result = 90;
  checkpoint.reset(); never.reset(); exited.reset();
  const int shutdown = app.Shutdown();
  const auto threads_after = p::detail::GetThreadCount();
  std::fprintf(stderr, "MW3_LIFECYCLE_SHUTDOWN:result=%d threads_before=%llu threads_after=%llu\n",
               shutdown, static_cast<unsigned long long>(threads_before), static_cast<unsigned long long>(threads_after));
  if (shutdown != 0 || threads_before != threads_after) return 90;
  std::fprintf(stderr, "MW3_LIFECYCLE_COMPLETE:exit=%d\n", result);
  return result;
}
REX_CONSOLE_APP_MAIN(LifecycleApp, RunLifecycle)
