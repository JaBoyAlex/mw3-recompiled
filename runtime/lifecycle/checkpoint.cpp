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
#include <rex/kernel/heap.h>
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
#include <thread>
#ifdef MW3_ALLOCATION_EXECUTE
#include MW3_SDK_TEST_ACCESS_HEADER
#endif
#if REX_PLATFORM_WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

bool VerifyProbeImportStops(rex::kernel::TitleRuntime&);
extern "C" void __imp__RtlImageXexHeaderField(PPCContext&, u8*);
extern "C" void __imp__NtAllocateVirtualMemory(PPCContext&, u8*);
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
#ifdef MW3_ALLOCATION_EXECUTE
Function original_allocation = nullptr;
#endif
p::DynamicLibrary kernel_library;
#ifdef MW3_ALLOCATION_INSPECT
std::atomic<unsigned> allocation_inputs = 0;
bool allocation_checked = false, omit_completion = false;
#endif

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
#ifdef MW3_ALLOCATION_INSPECT
u32 LoadRawWord(u32 address) {
  std::array<std::byte, 4> bytes{};
  Require(bool(current->GetGuestMemory().CopyFrom(address, bytes)), "allocation word read failed");
  u32 value = 0;
  for (auto byte : bytes) value = (value << 8) | std::to_integer<u32>(byte);
  return value;
}
#endif
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
#ifdef MW3_ALLOCATION_EXECUTE
  original_allocation = kernel_library.GetSymbol<Function>("__imp__NtAllocateVirtualMemory");
  Require(original_allocation && original_allocation != &__imp__NtAllocateVirtualMemory,
          "SDK allocation provider missing/interposed");
#endif
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
#ifdef MW3_ALLOCATION_INSPECT
  if (std::strcmp(name, "NtAllocateVirtualMemory") == 0) {
    const char* nonce = std::getenv("MW3_ALLOCATION_NONCE");
    Require(nonce && std::strlen(nonce) == 32, "allocation nonce missing");
    for (unsigned i = 0; i < 32; ++i)
      Require((nonce[i] >= '0' && nonce[i] <= '9') || (nonce[i] >= 'a' && nonce[i] <= 'f'), "allocation nonce invalid");
    std::fprintf(stderr, "MW3_ALLOCATION_ARMED:nonce=%s\n", nonce);
    Require(++allocation_inputs == 1, "allocation call budget exceeded");
    if (mode == "allocation-bad-pointer") {
      std::fprintf(stderr, "MW3_ALLOCATION_MUTATION:allocation-bad-pointer nonce=%s\n", nonce);
      ctx.r3.u32 ^= 1;
    }
    Require(ctx.lr == MW3_ALLOCATION_LR, "allocation caller differs from audited PPC");
    Require(u64(ctx.r31.u32) + 328 <= 0x100000000ull &&
            ctx.r3.u32 == ctx.r31.u32 + 80 && ctx.r4.u32 == ctx.r31.u32 + 324,
            "allocation pointer setup differs from audited PPC");
    Require(ctx.r5.u32 == 0x60002000u && ctx.r6.u32 == 4 && ctx.r7.u32 == ctx.r27.u32,
            "allocation value setup differs from audited PPC");
    auto& memory = current->GetGuestMemory();
    for (u32 address : {ctx.r3.u32, ctx.r4.u32}) {
      Require(address && !(address & 3u) && bool(memory.GetReadOnlySpan(address, 4)) &&
              bool(memory.GetWritableSpan(address, 4)), "allocation word is not mapped read/write");
    }
    const u32 base_word = ctx.r3.u32, size_word = ctx.r4.u32;
    const u32 input_base = LoadRawWord(base_word), input_size = LoadRawWord(size_word);
#ifdef MW3_ALLOCATION_VALUES
    Require(input_base == MW3_ALLOCATION_INITIAL_BASE && input_size == MW3_ALLOCATION_INITIAL_SIZE &&
            ctx.r7.u32 == MW3_ALLOCATION_REGION, "allocation input differs from captured contract");
#endif
    std::fprintf(stderr, "MW3_ALLOCATION_INPUT:lr=%08x r1=%08x r31=%08x base_word=%08x size_word=%08x base=%08x size=%08x type=%08x protect=%08x region=%08x nonce=%s\n",
                 u32(ctx.lr), ctx.r1.u32, ctx.r31.u32, ctx.r3.u32, ctx.r4.u32,
                 input_base, input_size, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32, nonce);
#ifdef MW3_ALLOCATION_EXECUTE
    Require(input_base == 0 && input_size && input_size <= MW3_ALLOCATION_LIMIT &&
            input_size <= 0x7fffffffu, "allocation reservation exceeds audited budget");
    std::array<std::byte, 12> base_before{}, size_before{}, after{};
    Require(bool(memory.CopyFrom(base_word - 4, base_before)) && bool(memory.CopyFrom(size_word - 4, size_before)),
            "allocation neighbour snapshot failed");
    auto& space = k::GetAddressSpace(*current);
    const auto title_pages = space.GetTitlePages();
    const u32 rounded = u32((u64(input_size) + 65535) & ~u64{65535});
    std::fprintf(stderr, "MW3_ALLOCATION_CALL:nonce=%s\n", nonce);
    original_allocation(ctx, static_cast<u8*>(current->GetMembase().GetBase()));
    const u32 result_base = LoadRawWord(base_word), result_size = LoadRawWord(size_word);
    std::fprintf(stderr, "MW3_ALLOCATION_RETURN:status=%08x base=%08x size=%08x nonce=%s\n",
                 ctx.r3.u32, result_base, result_size, nonce);
    Require(ctx.r3.u32 == 0, "allocation SDK status differs from audited success");
    auto* heap = space.LookupHeap(result_base);
    k::HeapAllocation allocation{}, last{};
    Require(result_base && !(result_base & 65535u) && result_size == rounded &&
            u64(result_base) + result_size <= 0x100000000ull && heap &&
            heap->GetHeapType() == k::HeapType::kGuestVirtual && heap->GetPageSize() == 65536 &&
            heap->QueryRegionInfo(result_base, &allocation) && allocation.allocation_base == result_base &&
            allocation.allocation_size == rounded && allocation.state == k::kMemoryAllocationReserve &&
            heap->QueryRegionInfo(result_base + rounded - 1, &last) && last.allocation_base == result_base &&
            last.allocation_size == rounded && last.state == k::kMemoryAllocationReserve &&
            !memory.GetReadOnlySpan(result_base, 4) && !memory.GetWritableSpan(result_base, 4) &&
            !memory.GetReadOnlySpan(result_base + rounded - 4, 4) &&
            !memory.GetWritableSpan(result_base + rounded - 4, 4) &&
            title_pages == space.GetTitlePages(), "allocation output differs from independent oracle");
    for (auto pair : {std::pair{base_word, &base_before}, std::pair{size_word, &size_before}}) {
      Require(bool(memory.CopyFrom(pair.first - 4, after)), "allocation neighbour recheck failed");
      for (unsigned i = 0; i < 12; ++i)
        if (i < 4 || i >= 8) Require(after[i] == (*pair.second)[i], "allocation changed neighbouring bytes");
    }
    allocation_checked = true;
    std::fprintf(stderr, "MW3_ALLOCATION_CHECK_PASS:bytes=%08x reserved=1 committed=0 neighbours=1 nonce=%s\n", rounded, nonce);
    if (mode == "allocation-bad-oracle") {
      std::fprintf(stderr, "MW3_ALLOCATION_MUTATION:allocation-bad-oracle nonce=%s\n", nonce);
      Require(result_size == rounded + 65536, "intentional allocation oracle mismatch");
    }
    if (mode == "allocation-late" || mode == "allocation-incomplete") {
      std::fprintf(stderr, "MW3_ALLOCATION_MUTATION:%s nonce=%s\n", mode.c_str(), nonce);
      std::fflush(stderr);
      if (mode == "allocation-late") std::this_thread::sleep_for(std::chrono::seconds(40));
      else omit_completion = true;
    }
    diagnostic = name;
    diagnostic_code = 86;
    std::fprintf(stderr, "MW3_ALLOCATION_STOP:before_guest_return=1 nonce=%s\n", nonce);
    throw rex::ThreadStop{86};
#endif
  }
#endif
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
#ifdef MW3_ALLOCATION_INSPECT
    const char* nonce = std::getenv("MW3_ALLOCATION_NONCE");
    Require(nonce && std::strlen(nonce) == 32, "checkpoint nonce missing");
    for (unsigned i = 0; i < 32; ++i)
      Require((nonce[i] >= '0' && nonce[i] <= '9') || (nonce[i] >= 'a' && nonce[i] <= 'f'), "checkpoint nonce invalid");
    std::fprintf(stderr, "MW3_CHECKPOINT_RUN:case=%s nonce=%s\n", mode.c_str(), nonce);
#endif
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
#ifdef MW3_ALLOCATION_INSPECT
    if (mode == "positive") {
#ifdef MW3_ALLOCATION_EXECUTE
      Require(allocation_inputs == 1 && allocation_checked, "allocation checkpoint missing");
#else
      Require(allocation_inputs == 1 && !allocation_checked, "read-only allocation inspection missing");
#endif
    }
#endif
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
#ifdef MW3_ALLOCATION_EXECUTE
  original_allocation = nullptr;
#endif
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
#ifdef MW3_ALLOCATION_INSPECT
  if (!omit_completion)
#endif
    std::fprintf(stderr, "MW3_LIFECYCLE_COMPLETE:exit=%d\n", result);
  return result;
}
REX_CONSOLE_APP_MAIN(LifecycleApp, RunLifecycle)
