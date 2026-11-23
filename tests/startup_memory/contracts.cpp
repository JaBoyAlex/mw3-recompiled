// SPDX-License-Identifier: GPL-3.0-only
// Original game-free native callbacks into the selected SDK's actual import thunks.
#include <rex/app/app.h>
#include <rex/kernel/export.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/object/kernel_thread.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/types/memory.h>
#include <rex/kernel/types/thread.h>
#include <rex/platform/thread.h>
#include <rex/ppc/image.h>
#include <rex/ppc/recompiled_code.h>
#include "kernel/test_access.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

namespace {
namespace k = rex::kernel;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
struct Failure : std::runtime_error { using std::runtime_error::runtime_error; };
void Check(bool condition, const char* reason) { if (!condition) throw Failure(reason); }
struct TestApp : rex::app::App {
  TestApp() : App("mw3_allocation_imports") {}
  rex::AppSysRequirements GetRequirements() const override { return {}; }
};
struct State {
  k::TitleRuntime* runtime = nullptr;
  u32 scratch = 0;
  std::string scenario, failure, nonce;
  unsigned verified = 0;
  std::atomic<bool> complete = false;
};
State* active = nullptr;
void Store(u32 at, u32 value) {
  std::array<std::byte, 4> bytes{std::byte(value >> 24), std::byte((value >> 16) & 255),
                                std::byte((value >> 8) & 255), std::byte(value & 255)};
  Check(bool(active->runtime->GetGuestMemory().CopyTo(at, bytes)), "fixture store failed");
}
u32 Load(u32 at) {
  std::array<std::byte, 4> bytes{};
  Check(bool(active->runtime->GetGuestMemory().CopyFrom(at, bytes)), "fixture load failed");
  u32 value = 0;
  for (auto byte : bytes) value = (value << 8) | std::to_integer<u32>(byte);
  return value;
}
u32 Call(PPCContext& ctx, std::uint8_t* base, const char* name, std::initializer_list<u32> values) {
  auto exports = k::GetExports(k::ExportModule::kXboxkrnl);
  auto found = std::find_if(exports.begin(), exports.end(), [&](const auto& row) { return row.name == name; });
  Check(found != exports.end() && found->fn, "required real kernel export missing");
  Check(found->type == k::ExportType::kFunction &&
        found->ordinal == (std::string(name) == "NtAllocateVirtualMemory" ? 0xcc : 0xdc),
        "export ordinal/type mismatch");
  PPCRegister* registers[] = {&ctx.r3, &ctx.r4, &ctx.r5, &ctx.r6, &ctx.r7, &ctx.r8};
  Check(values.size() <= 6, "fixture argument count exceeded");
  unsigned index = 0;
  for (auto value : values) registers[index++]->u64 = value;
  std::fprintf(stderr, "MW3_ALLOC_CALL:%s\n", name);
  found->fn(ctx, base);
  std::fprintf(stderr, "MW3_ALLOC_RETURN:%s status=%08x\n", name, ctx.r3.u32);
  return ctx.r3.u32;
}
void Scenario(PPCContext& ctx, std::uint8_t* base, const std::string& scenario) {
    const auto cell = active->scratch + 16;
    const auto size_cell = cell + 4;
    const auto size_argument = size_cell + (scenario == "physical-alias" ? 0x20000000u : 0u);
    auto& memory = active->runtime->GetGuestMemory();
    const auto pages = k::GetAddressSpace(*active->runtime).GetTitlePages();
    // Reset the entire scratch prefix; every rejection must preserve it byte-for-byte.
    std::array<std::byte, 64> original{};
    original.fill(std::byte{0x6d});
    Check(bool(memory.CopyTo(active->scratch, original)), "scratch initialization failed");
    Store(active->scratch + 12, 0xa5110046);
    Store(cell, 0);
    Store(size_cell, scenario == "negative-intmin" ? 0x80000000u : scenario == "negative-small" ? 0xffffffefu : 17);
    Store(cell + 8, 0xb6220046);
    const bool pointer_case = scenario.starts_with("alloc-") || scenario.starts_with("free-");
    if (pointer_case) {
      const bool freeing = scenario.starts_with("free-");
      u32 ptr_base = cell, ptr_size = size_cell;
      u32 flags = freeing ? u32(k::kXMemRelease) : u32(k::kXMemReserve | k::kXMemCommit);
      u32 protection = k::kXPageReadWrite, region = 0;
      const auto kind = scenario.substr(freeing ? 5 : 6);
      const bool size_pointer = kind.ends_with("-size");
      u32 owned = 0;
      if (freeing && kind != "unallocated") {
        Check(Call(ctx, base, "NtAllocateVirtualMemory", {cell, size_cell,
              u32(k::kXMemReserve | k::kXMemCommit), k::kXPageReadWrite, 0}) == 0, "free rejection setup failed");
        owned = Load(cell);
        Store(owned, 0x46271828);
        Store(size_cell, 0);
      }
      u32 bad = size_pointer ? size_cell : cell;
      if (kind.starts_with("null-")) bad = 0;
      else if (kind.starts_with("unaligned-")) { bad = active->scratch + 33; Store(bad, 17); }
      else if (kind.starts_with("outside-")) bad = 0xdead0000u;
      else if (kind.starts_with("wrapping-")) bad = 0xfffffffeu;
      else if (kind.starts_with("readonly-")) { /* Initialized valid word, protected below. */ }
      else if (kind == "zero-size") Store(size_cell, 0);
      else if (kind == "type") flags = 1;
      else if (kind == "protection") protection = 0;
      else if (kind == "region") region = 3;
      else if (kind == "alias") ptr_size = cell;
      else if (kind == "alias-physical") ptr_size = cell + 0x20000000u;
      else if (kind != "unallocated") throw Failure("unknown rejection scenario");
      if (kind.ends_with("-base") || size_pointer) {
        if (size_pointer) ptr_size = bad; else ptr_base = bad;
      }
      if (kind.starts_with("null-") || kind.starts_with("outside-") || kind.starts_with("wrapping-"))
        Check(!memory.GetReadOnlySpan(bad, 4) && !memory.GetWritableSpan(bad, 4),
              "invalid-pointer fixture unexpectedly has checked access");
      Check(bool(memory.CopyFrom(active->scratch, original)), "scratch snapshot failed");
      if (kind.starts_with("readonly-"))
        Check(bool(memory.Protect(active->scratch, 4096, k::GuestProtect::kReadOnly)), "readonly fixture failed");
      if (kind.starts_with("readonly-"))
        Check(bool(memory.GetReadOnlySpan(bad, 4)) && !memory.GetWritableSpan(bad, 4),
              "readonly fixture has incorrect access");
      const auto status = freeing
          ? Call(ctx, base, "NtFreeVirtualMemory", {ptr_base, ptr_size, flags, region})
          : Call(ctx, base, "NtAllocateVirtualMemory", {ptr_base, ptr_size, flags, protection, region});
      Check(status != 0, "invalid argument returned success");
      std::array<std::byte, 64> after{};
      Check(bool(memory.CopyFrom(active->scratch, after)) && after == original,
            "rejected call changed scratch/in-out bytes");
      if (kind.starts_with("readonly-"))
        Check(bool(memory.Protect(active->scratch, 4096, k::GuestProtect::kReadWrite)), "scratch protection recovery failed");
      if (kind == "type" || kind == "region" || kind == "zero-size" || kind == "alias" || kind == "alias-physical")
        Check(status == 0xc000000du, "selected-policy invalid-parameter status mismatch");
      if (kind == "protection") Check(status == 0xc0000045u, "invalid-protection status mismatch");
      if (owned) {
        Check(Load(owned) == 0x46271828, "invalid free damaged live allocation");
        Store(cell, owned); Store(size_cell, 0);
        Check(Call(ctx, base, "NtFreeVirtualMemory", {cell, size_cell, k::kXMemRelease, 0}) == 0,
              "free rejection cleanup failed");
      }
    } else if (scenario == "lifecycle") {
      const auto allocate = [&](u32 at, u32 length, u32 flags) {
        Store(cell, at); Store(size_cell, length);
        Check(Call(ctx, base, "NtAllocateVirtualMemory", {cell, size_cell, flags, k::kXPageReadWrite, 0}) == 0,
              "lifecycle allocation failed");
      };
      allocate(0, 0x3000, k::kXMemReserve);
      const auto address = Load(cell);
      Check(address && address % 65536 == 0 && Load(size_cell) == 65536, "reserve geometry mismatch");
      Check(!memory.GetReadOnlySpan(address, 4), "reservation is readable before commitment");
      allocate(address, 65536, k::kXMemCommit);
      Check(Load(cell) == address && Load(size_cell) == 65536, "commit in-out mismatch");
      Store(address, 0x31415926); Store(address + 65532, 0x27182818);
      Store(cell, address); Store(size_cell, 1);
      Check(Call(ctx, base, "NtFreeVirtualMemory", {cell, size_cell, k::kXMemDecommit, 0}) == 0,
            "decommit import failed");
      Check(Load(cell) == address && Load(size_cell) == 4096, "decommit rounding/endian mismatch");
      Check(!memory.GetReadOnlySpan(address, 4) && !memory.GetWritableSpan(address, 4),
            "decommitted page remained accessible");
      Check(Load(address + 65532) == 0x27182818, "decommit corrupted committed neighbour");
      allocate(address, 4096, k::kXMemCommit);
      Check(Load(address) == 0 && Load(address + 65532) == 0x27182818, "recommit zero/preservation mismatch");
      Store(cell, address); Store(size_cell, 0);
      Check(Call(ctx, base, "NtFreeVirtualMemory", {cell, size_cell, k::kXMemRelease, 0}) == 0,
            "lifecycle release failed");
      Check(Load(cell) == address && Load(size_cell) == 65536 && !memory.GetReadOnlySpan(address, 4),
            "release output/state mismatch");
    } else {
      const bool huge = scenario == "negative-intmin";
      const auto status = Call(ctx, base, "NtAllocateVirtualMemory",
          {cell, size_argument, u32(k::kXMemReserve) | (huge ? 0u : u32(k::kXMemCommit)), k::kXPageReadWrite, 0});
      if (!huge) Check(status == 0, "small reserve+commit failed");
      if (status == 0) {
        const auto address = Load(cell), length = Load(size_cell);
        Check(address && address % 65536 == 0, "chosen address not nonzero/granularity aligned");
        Check(length == (huge ? 0x80000000u : 65536u), "rounded output size/endian ABI mismatch");
        if (!huge) {
          Check(Load(address) == 0 && Load(address + length - 4) == 0, "fresh committed allocation not zeroed");
          Store(address, 0x12345678);
          Store(address + length - 4, 0x87654321);
          Check(Load(address) == 0x12345678 && Load(address + length - 4) == 0x87654321,
                "allocated edge words did not round-trip");
        }
        if (scenario == "physical-alias") {
          u32 alias_base = 0, alias_size = 0;
          for (unsigned byte = 0; byte < 4; ++byte) {
            alias_base = (alias_base << 8) | base[cell + 0x20000000u + byte];
            alias_size = (alias_size << 8) | base[size_argument + byte];
          }
          Check(alias_base == address && alias_size == length, "physical in-out alias is incoherent");
        }
        Store(size_cell, 0);
        Check(Call(ctx, base, "NtFreeVirtualMemory", {cell, size_argument, k::kXMemRelease, 0}) == 0,
              "whole-reservation release failed");
        Check(Load(cell) == address && Load(size_cell) == length, "release output words differ");
        Check(!active->runtime->GetGuestMemory().GetReadOnlySpan(address, 4), "released allocation remained checked-readable");
        if (scenario == "double-release") {
          Store(size_cell, 0);
          Check(Call(ctx, base, "NtFreeVirtualMemory", {cell, size_cell, k::kXMemRelease, 0}) != 0,
                "double release returned success");
          Check(Load(cell) == address && Load(size_cell) == 0, "double release changed in-out cells");
        }
      } else {
        Check(Load(cell) == 0 && Load(cell + 4) == 0x80000000u, "failed large reserve changed its in/out cells");
      }
    }
    Check(Load(active->scratch + 12) == 0xa5110046 && Load(active->scratch + 24) == 0xb6220046,
          "in/out pointer operation overwrote neighbouring canaries");
    Check(pages == k::GetAddressSpace(*active->runtime).GetTitlePages(), "scenario title-page accounting leaked");
    ++active->verified;
    std::fprintf(stderr, "MW3_ALLOC_VERIFIED:case=%s\n", scenario.c_str());
}
void Entry(PPCContext& ctx, std::uint8_t* base) {
  try {
    std::fprintf(stderr, "MW3_ALLOC_ARMED:case=%s nonce=%s\n", active->scenario.c_str(), active->nonce.c_str());
    if (active->scenario == "repeat") {
      for (unsigned round = 0; round < 3; ++round) {
        for (const auto* scenario : round % 2 ? std::array{"double-release", "negative-small", "lifecycle", "basic"}
                                            : std::array{"basic", "lifecycle", "negative-small", "double-release"})
          Scenario(ctx, base, scenario);
      }
    } else if (active->scenario.starts_with("mutation-")) {
      Scenario(ctx, base, "basic");
      std::fprintf(stderr, "MW3_ALLOC_MUTATION:%s\n", active->scenario.c_str());
      std::fflush(stderr);
      if (active->scenario == "mutation-result") throw Failure("intentional wrong result");
      if (active->scenario == "mutation-incomplete") {
        ctx.r3.u64 = 0;
        active->complete.store(true, std::memory_order_release);
        return;
      }
      if (active->scenario == "mutation-late") std::this_thread::sleep_for(std::chrono::seconds(40));
      throw Failure("unknown mutation");
    } else {
      Scenario(ctx, base, active->scenario);
    }
    ctx.r3.u64 = 0;
  } catch (const Failure& error) {
    active->failure = error.what();
    ctx.r3.u64 = 42;
  }
  active->complete.store(true, std::memory_order_release);
}
constexpr u32 entry = 0x82101000;
const PPCFuncMapping mappings[] = {{entry, &Entry}, {0, nullptr}};
const rex::ppc::PPCImage image{0x82100000, 0x10000, 0x82000000, 0x200000, mappings};

int Run(TestApp& app, const rex::CLIArgList& args) {
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
#endif
  const char* nonce = std::getenv("MW3_ALLOC_NONCE");
  const std::string session = nonce ? nonce : "";
  if (session.size() != 32 || session.find_first_not_of("0123456789abcdef") != std::string::npos)
    return 2;
  const auto before = rex::platform::detail::GetThreadCount();
  if (!app.Init(args)) return 2;
  auto runtime = std::make_unique<k::TitleRuntime>(image);
  State state;
  state.runtime = runtime.get();
  const char* chosen = std::getenv("MW3_ALLOC_CASE");
  state.scenario = chosen ? chosen : "";
  state.nonce = session;
  int result = 2;
  try {
    Check(bool(runtime->GetTitlePaths().entry.Set("")), "empty synthetic entry rejected");
    Check(bool(runtime->Load()), "synthetic load failed");
    auto allocated = runtime->GetGuestMemory().Allocate(65536, 4096, k::GuestProtect::kReadWrite,
        state.scenario == "physical-alias" || state.scenario.ends_with("alias-physical")
            ? k::GuestHeap::kPhysical : k::GuestHeap::kSystem);
    Check(bool(allocated), "scratch allocation failed");
    state.scratch = *allocated;
    active = &state;
    const auto handles_before = runtime->GetObjectTable().GetAll().size();
    const auto pages_before = k::GetAddressSpace(*runtime).GetTitlePages();
    auto worker = std::make_unique<k::KernelThread>(*runtime, 65536, 0, entry, 0x4601, 0, true, false);
    auto started = runtime->GetThreadRegistry().Launch(std::move(worker));
    Check(bool(started), "synthetic callback launch failed");
    u64 timeout = u64(-std::int64_t{100000000});
    Check(runtime->GetThreadRegistry().GetObjectWaiter().WaitGuestObject(*started, 0, 0, 0, &timeout) == 0,
          "callback deadline expired");
    auto pin = runtime->GetThreadRegistry().FindByHandle(*started);
    Check(bool(pin), "completed callback handle missing");
    auto metadata = runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());
    Check(bool(metadata) && metadata->terminated == 1, "callback termination metadata missing");
    const auto exit = u32(metadata->exit_status);
    pin.Reset();
    k::CloseOwned(runtime->GetObjectTable(), *started);
    Check(state.complete.load(std::memory_order_acquire), "callback did not complete");
    if (!state.failure.empty()) throw Failure(state.failure);
    Check(exit == 0, "callback returned unexpected status");
    Check(handles_before == runtime->GetObjectTable().GetAll().size(), "kernel handle accounting did not recover");
    Check(pages_before == k::GetAddressSpace(*runtime).GetTitlePages(), "title-page accounting did not recover");
    Check(bool(runtime->GetGuestMemory().Free(state.scratch)), "scratch release failed");
    state.scratch = 0;
    result = 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "MW3_ALLOC_FAILURE:%s\n", error.what());
  }
  active = nullptr;
  runtime->Unload();
  Check(!runtime->IsLoaded(), "runtime remained loaded");
  runtime.reset();
  Check(k::GetProcessRuntime() == nullptr, "process runtime remained installed");
  const auto shutdown = app.Shutdown();
  const auto after = rex::platform::detail::GetThreadCount();
  if (shutdown || before != after) result = 2;
  if (state.scenario == "mutation-incomplete") return result;
  std::fprintf(stderr, "MW3_ALLOC_COMPLETE:case=%s result=%d verified=%u threads_before=%llu threads_after=%llu nonce=%s\n",
               state.scenario.c_str(), result, state.verified, static_cast<unsigned long long>(before), static_cast<unsigned long long>(after), state.nonce.c_str());
  return result;
}
}  // namespace
REX_CONSOLE_APP_MAIN(TestApp, Run)
