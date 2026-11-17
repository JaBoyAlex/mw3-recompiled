// SPDX-License-Identifier: GPL-3.0-only
// Original fixtures; no game-derived bytes or semantics oracle from generated code.
#define PPC_CONFIG_H_INCLUDED
#include <ppc_context.h>
#include <array>
#include <bit>
#include <iostream>
#include <string_view>
PPC_FUNC(arithmetic_0);
PPC_FUNC(memory_0);
PPC_FUNC(branch_0);
PPC_FUNC(rotate_0);
int main(int argc, char** argv) {
    const bool mutate = argc == 2 && std::string_view(argv[1]) == "--mutate-oracle";
    alignas(32) std::array<uint8_t, 4096> memory{};
    unsigned failures = 0;
    auto check = [&](bool value) { if (!value) ++failures; };
    uint64_t seed = 0x12345678abcdef01ULL;
    for (unsigned i = 0; i < 256; ++i) {
        seed = seed * 6364136223846793005ULL + 1;
        PPCContext ctx{};
        ctx.r3.u64 = seed;
        ctx.r4.u64 = std::rotl(seed, 29);
        const uint64_t expected = ctx.r3.u64 + ctx.r4.u64;
        arithmetic_0(ctx, memory.data());
        check(ctx.r3.u64 == (expected ^ (mutate ? 1ULL : 0ULL)));
        ctx.r3.u64 = static_cast<uint32_t>(seed);
        const auto rotated = std::rotl(static_cast<uint32_t>(seed), 8);
        rotate_0(ctx, memory.data());
        check(ctx.r3.u64 == rotated);
    }
    for (const auto value : {0U, 1U, 0x11223344U, 0x80000000U, 0xffffffffU}) {
        PPCContext ctx{};
        ctx.r3.u64 = value;
        ctx.r5.u64 = 64;
        memory_0(ctx, memory.data());
        check(ctx.r4.u64 == value && ctx.r6.u64 == (value >> 16) && ctx.r7.u64 == (value & 255));
        check(memory[64] == (value >> 24) && memory[65] == ((value >> 16) & 255)
            && memory[66] == ((value >> 8) & 255) && memory[67] == (value & 255));
    }
    for (const int32_t left : {-2147483647 - 1, -1, 0, 1, 2147483647}) {
        for (const int32_t right : {-2147483647 - 1, -1, 0, 1, 2147483647}) {
            PPCContext ctx{};
            ctx.r3.s64 = left;
            ctx.r4.s64 = right;
            branch_0(ctx, memory.data());
            check(ctx.r3.s64 == (left < right ? -1 : 1));
        }
    }
    std::cout << (failures ? "FAIL" : "PASS") << ": synthetic PPC arithmetic/rotation/endian/branch (547 checks; no VMX128 coverage)\n";
    return failures ? 1 : 0;
}
