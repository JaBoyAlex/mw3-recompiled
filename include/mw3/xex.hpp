// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
#include <cstdint>
#include <span>
#include <optional>
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
// Original bounded oracle for a complete raw header (through image_offset).
// Returns an immediate value for type 0, the inline value's guest address for
// type 1, or a bounded payload's guest address otherwise. Missing is distinct
// from a present immediate zero. No guest memory is dereferenced here.
std::optional<std::uint32_t> resolve_xex_optional_header(
    std::span<const std::byte> header, std::uint32_t guest_base, std::uint32_t key);
}
