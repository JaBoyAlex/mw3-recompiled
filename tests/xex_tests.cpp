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
}
int main() {
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
