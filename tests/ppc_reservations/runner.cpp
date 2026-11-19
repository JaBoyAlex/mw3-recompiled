// SPDX-License-Identifier: GPL-3.0-only
// Observations only: all load-reserve/conditional-store operations call actual
// generated instructions. The independent Python oracle judges their results.
#include "ppc_config.h"
#include "dispatch.h"
#include <rex/kernel/heap.h>
#include <rex/platform/thread.h>
#include <nlohmann/json.hpp>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#include <link.h>
#endif

namespace {
using Json = nlohmann::json;
constexpr u32 address = 0x10200;
constexpr u64 sentinel = 0xDEADBEEF13579BDF;
void Require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
std::string Module(const char* name) {
#ifdef _WIN32
    const auto module = GetModuleHandleW(std::filesystem::path(std::string(name) + ".dll").c_str());
    Require(module != nullptr, "missing-core-module");
    std::array<wchar_t, 32768> path{};
    const auto size = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
    Require(size && size < path.size(), "truncated-module-path");
    return std::filesystem::path(path.data()).generic_string();
#else
    const auto file = "lib" + std::string(name) + ".so";
    void* module = dlopen(file.c_str(), RTLD_NOLOAD | RTLD_NOW);
    Require(module != nullptr, "missing-core-module");
    link_map* map = nullptr;
    const bool ok = dlinfo(module, RTLD_DI_LINKMAP, &map) == 0 && map && map->l_name;
    const auto path = ok ? std::filesystem::absolute(map->l_name).string() : "";
    dlclose(module); Require(!path.empty(), "missing-module-path"); return path;
#endif
}
u64 Read(const u8* ptr, unsigned width) {
    u64 value = 0;
    for (unsigned i = 0; i < width; ++i) value = (value << 8) | ptr[i];
    return value;
}
void Write(u8* ptr, unsigned width, u64 value) {
    for (unsigned i = 0; i < width; ++i) { ptr[width - i - 1] = static_cast<u8>(value); value >>= 8; }
}
}
int main(int argc, char** argv) {
    try {
        Require(argc == 3, "case-file-and-nonce-required");
        const std::string nonce = argv[2];
        Require(nonce.size() == 32 && nonce.find_first_not_of("0123456789abcdef") == std::string::npos, "invalid-nonce");
        Require(std::filesystem::file_size(argv[1]) <= 4 * 1024 * 1024, "case-file-budget");
        std::ifstream stream(argv[1], std::ios::binary);
        const auto cases = Json::parse(stream);
        Require(cases.is_array() && !cases.empty() && cases.size() <= 1024, "invalid-case-count");
        const auto before = rex::platform::detail::GetThreadCount();
        Json rows = Json::array(), loaded;
        {
            rex::kernel::GuestAddressSpace memory;
            Require(memory.Initialize() && memory.InitializeFunctionTable(REX_CODE_BASE, REX_CODE_SIZE, REX_IMAGE_BASE, REX_IMAGE_SIZE),
                "guest-memory-initialization-failed");
            auto* heap = memory.LookupHeap(0x10000);
            Require(heap && heap->AllocFixed(0x10000, 0x10000, 0x1000,
                rex::kernel::kMemoryAllocationReserve | rex::kernel::kMemoryAllocationCommit,
                rex::kernel::kMemoryProtectRead | rex::kernel::kMemoryProtectWrite), "private-commit-failed");
            register_functions(memory);
            loaded = {{"rexkernel", Module("rexkernel")}, {"rexbase", Module("rexbase")}};
            std::cout << "MW3_RESERVATION_LIBRARIES:" << Json({{"nonce", nonce}, {"loaded", loaded}}).dump() << '\n' << std::flush;
            auto* base = memory.GetVirtualMembase();
            bool mutated = false;
            for (const auto& entry : cases) {
                const auto width = entry.at("width").get<unsigned>();
                const auto indexed = entry.at("indexed").get<bool>();
                const auto so = entry.at("so").get<unsigned>();
                const auto cr = entry.at("cr").get<unsigned>();
                Require((width == 4 || width == 8) && so <= 1 && cr <= 15, "invalid-case-scalar");
                const auto initial = entry.at("initial").get<u64>();
                const auto& steps = entry.at("steps");
                Require(steps.is_array() && !steps.empty() && steps.size() <= 8, "step-budget");
                std::memset(base + 0x10000, 0xa5, 0x10000);
                Write(base + address, width, initial);
                std::array<PPCContext, 2> contexts{};
                for (auto& ctx : contexts) {
                    ctx.r0.u64 = sentinel; // RA=0 must ignore this value.
                    ctx.r1.u64 = 0x18000;
                    ctx.r3.u64 = sentinel;
                    ctx.r4.u64 = 0x10000;
                    ctx.r6.u64 = indexed ? 0x200 : address;
                    ctx.r31.u64 = sentinel;
                    ctx.cr0.SetRaw(cr); ctx.cr1.SetRaw(0xA); ctx.xer.so = static_cast<u8>(so);
                }
                Json observations = Json::array();
                for (const auto& step : steps) {
                    const auto index = step.at("ctx").get<unsigned>();
                    const auto op = step.at("op").get<std::string>();
                    Require(index < 2 && (op == "load" || op == "store"), "invalid-step");
                    auto& ctx = contexts[index];
                    ctx.r5.u64 = step.at("value").get<u64>();
                    const auto function = "test_" + op + (width == 4 ? "_w" : "_d") + (indexed ? "_index" : "_zero");
                    const auto start = std::chrono::steady_clock::now();
                    dispatch(function, ctx, base);
                    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                        std::chrono::steady_clock::now() - start).count();
                    auto r3 = ctx.r3.u64;
                    if (std::getenv("MW3_RESERVATION_WRONG") && !mutated && op == "load") {
                        r3 ^= 1; mutated = true; // Deliberate observation mutation, after real execution.
                    }
                    bool guards = true;
                    for (u32 i = address - 16; i < address + width + 16; ++i)
                        if ((i < address || i >= address + width) && base[i] != 0xa5) guards = false;
                    observations.push_back({{"r3", r3}, {"cr", ctx.cr0.GetRaw()}, {"so", ctx.xer.so},
                        {"memory", Read(base + address, width)}, {"guards", guards},
                        {"preserved", ctx.r0.u64 == sentinel && ctx.r31.u64 == sentinel && ctx.cr1.GetRaw() == 0xA &&
                            ctx.r4.u64 == 0x10000 && ctx.r6.u64 == (indexed ? 0x200 : address)},
                        {"ns", elapsed}});
                }
                rows.push_back({{"id", entry.at("id")}, {"steps", observations}});
            }
            Require(heap->Release(0x10000, nullptr), "private-commit-release-failed");
            // Destruction below releases this lane's reservation/function table.
        }
        const auto after = rex::platform::detail::GetThreadCount();
        Require(before == after, "tracked-thread-count-changed");
        if (std::getenv("MW3_RESERVATION_INCOMPLETE")) {
            std::cout << "MW3_RESERVATION_INCOMPLETE:" << nonce << '\n'; return 43;
        }
        std::cout << "MW3_RESERVATION_COMPLETE:" << Json({{"schema", 1}, {"nonce", nonce}, {"loaded", loaded},
            {"threads_before", before}, {"threads_after", after}, {"memory_destroyed", true}, {"cases", rows}}).dump() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_RESERVATION_ERROR:" << error.what() << '\n'; return 2;
    }
}
