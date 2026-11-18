// SPDX-License-Identifier: GPL-3.0-only
#include "mw3/xex.hpp"
#include <iostream>
#include <string_view>

namespace {
void put(std::vector<std::byte>& b, std::size_t offset, std::uint32_t v) {
    for (std::size_t i = 0; i < 4; ++i) b[offset + i] = static_cast<std::byte>((v >> (24 - i * 8)) & 255);
}
std::vector<std::byte> fixture() {
    std::vector<std::byte> b(32);
    b[0] = std::byte{'X'}; b[1] = std::byte{'E'}; b[2] = std::byte{'X'}; b[3] = std::byte{'2'};
    put(b, 4, 0x12345678); put(b, 8, 128); put(b, 16, 64); put(b, 20, 1);
    put(b, 24, 0x40006); put(b, 28, 0x87654321);
    return b;
}
int failures = 0;
void check(bool ok, std::string_view name) {
    if (!ok) { std::cerr << "FAIL: " << name << '\n'; ++failures; }
}
void rejects(const std::vector<std::byte>& b, std::uint64_t size, std::string_view name) {
    try { (void)mw3::inspect_xex(b, size); check(false, name); } catch (const mw3::XexError&) {}
}
void header_rejects(const std::vector<std::byte>& b, std::uint32_t base, std::uint32_t key, std::string_view name) {
    try { (void)mw3::resolve_xex_optional_header(b, base, key); check(false, name); }
    catch (const mw3::XexError&) {}
}
void header_queries() {
    auto bytes = fixture(); bytes.resize(128);
    constexpr std::uint32_t base = 0x10000000;
    auto query = [&](std::uint32_t key) { return mw3::resolve_xex_optional_header(bytes, base, key); };
    put(bytes, 24, 0x10000); put(bytes, 28, 0x12345678);
    check(query(0x10000) == 0x12345678, "immediate header value");
    put(bytes, 28, 0); check(query(0x10000).has_value() && *query(0x10000) == 0, "present immediate zero");
    check(!query(0x20000), "missing header distinct from zero");
    put(bytes, 24, 0x20001); check(query(0x20001) == base + 28, "inline field address");
    put(bytes, 24, 0x30002); put(bytes, 28, 120);
    check(query(0x30002) == base + 120, "fixed field at final valid boundary");
    put(bytes, 28, 124); header_rejects(bytes, base, 0x30002, "fixed payload crosses header end");
    put(bytes, 24, 0x400ff); put(bytes, 28, 120); put(bytes, 120, 8);
    check(query(0x400ff) == base + 120, "variable field boundary");
    for (auto length : {0u, 3u, 9u, 0xffffffffu}) {
        put(bytes, 120, length); header_rejects(bytes, base, 0x400ff, "invalid variable payload size");
    }
    put(bytes, 120, 8);
    for (auto offset : {0u, 28u, 119u, 128u, 0xffffffffu}) {
        put(bytes, 28, offset); header_rejects(bytes, base, 0x400ff, "invalid payload offset");
    }
    put(bytes, 28, 120);
    header_rejects(bytes, 0xffffffc0, 0x400ff, "guest pointer wrap");
    header_rejects(bytes, base + 1, 0x400ff, "unaligned guest header");
    for (std::size_t n = 0; n < bytes.size(); ++n)
        header_rejects(std::vector(bytes.begin(), bytes.begin() + n), base, 0x400ff, "every incomplete raw span");
    put(bytes, 20, 2); put(bytes, 32, 0x400ff); put(bytes, 36, 120);
    header_rejects(bytes, base, 0x400ff, "duplicate selected key");
    header_rejects(bytes, base, 0x50000, "duplicate unrelated key");
}
}
int main() {
    header_queries();
    auto b = fixture();
    const auto h = mw3::inspect_xex(b, 256);
    check(h.module_flags == 0x12345678 && h.image_offset == 128 && h.security_offset == 64, "big endian fields");
    check(h.optional.size() == 1 && h.optional[0].value == 0x87654321 && h.optional[0].key == 0x40006, "optional metadata");
    for (std::size_t length = 0; length < 32; ++length)
        rejects(std::vector(b.begin(), b.begin() + length), 256, "every truncated prefix");
    b[0] = std::byte{'P'}; rejects(b, 256, "wrong magic");
    b = fixture(); put(b, 20, 0xffffffff); rejects(b, 256, "overflow count");
    b = fixture(); put(b, 8, 256); rejects(b, 256, "image at EOF");
    b = fixture(); put(b, 8, 31); rejects(b, 256, "image overlaps metadata");
    b = fixture(); put(b, 16, 256); rejects(b, 256, "security at EOF");
    b = fixture(); put(b, 16, 0); rejects(b, 256, "security overlaps metadata");
    rejects(fixture(), 12, "inconsistent supplied file size");
    b = fixture(); put(b, 20, 0); b.resize(24);
    check(mw3::inspect_xex(b, 256).optional.empty(), "zero optional headers");
    // Deterministically exercise hostile count/offset combinations; success must remain bounded.
    std::uint32_t seed = 12345;
    for (int i = 0; i < 10000; ++i) {
        b = fixture(); seed = seed * 1664525u + 1013904223u;
        put(b, 20, seed); put(b, 8, seed ^ 0x55555555u);
        try { const auto value = mw3::inspect_xex(b, 256); check(value.optional.size() <= 1, "bounded output"); }
        catch (const mw3::XexError&) {}
    }
    std::cout << (failures ? "FAIL" : "PASS") << ": XEX metadata parser (synthetic fixtures only)\n";
    return failures ? 1 : 0;
}
