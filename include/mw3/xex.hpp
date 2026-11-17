// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <vector>

namespace mw3 {
struct XexError : std::runtime_error { using std::runtime_error::runtime_error; };
struct OptionalHeader { std::uint32_t key; std::uint32_t value; };
struct XexHeader {
    std::uint32_t module_flags;
    std::uint32_t image_offset;
    std::uint32_t security_offset;
    std::vector<OptionalHeader> optional;
};
// Only inspect metadata. No decryption, execution, title identification or trust decision.
// Supply the prefix through the optional table, and the actual complete file size.
inline constexpr std::size_t max_xex_metadata = 1024 * 1024;
XexHeader inspect_xex(std::span<const std::byte> prefix, std::uint64_t file_size);
}
