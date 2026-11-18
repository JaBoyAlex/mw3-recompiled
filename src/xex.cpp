// SPDX-License-Identifier: GPL-3.0-only
#include "mw3/xex.hpp"
#include <array>
#include <unordered_set>

namespace mw3 {
namespace {
std::uint32_t be32(std::span<const std::byte> bytes, std::size_t at) {
    if (at > bytes.size() || bytes.size() - at < 4) throw XexError("truncated XEX header");
    std::uint32_t value = 0;
    for (std::size_t i = 0; i < 4; ++i) value = (value << 8) | std::to_integer<std::uint32_t>(bytes[at + i]);
    return value;
}
}
XexHeader inspect_xex(std::span<const std::byte> prefix, std::uint64_t file_size) {
    if (prefix.size() < 24 || file_size < prefix.size()) throw XexError("invalid XEX prefix or file size");
    constexpr std::array magic{std::byte{'X'}, std::byte{'E'}, std::byte{'X'}, std::byte{'2'}};
    for (std::size_t i = 0; i < magic.size(); ++i)
        if (prefix[i] != magic[i]) throw XexError("expected XEX2 magic");
    const auto count = be32(prefix, 20);
    // Bound count before multiplication/allocation, including on a 32-bit host.
    if (count > (max_xex_metadata - 24) / 8) throw XexError("XEX metadata exceeds inspection limit");
    const std::size_t end = 24 + static_cast<std::size_t>(count) * 8;
    if (end > prefix.size()) throw XexError("truncated XEX optional table");
    XexHeader header{be32(prefix, 4), be32(prefix, 8), be32(prefix, 16), {}};
    if (header.image_offset < end || header.image_offset >= file_size)
        throw XexError("XEX image offset is outside file payload");
    if (header.security_offset < end || header.security_offset >= file_size)
        throw XexError("XEX security offset is outside file");
    header.optional.reserve(count);
    for (std::size_t i = 0; i < count; ++i)
        header.optional.push_back({be32(prefix, 24 + i * 8), be32(prefix, 28 + i * 8)});
    return header;
}

std::optional<std::uint32_t> resolve_xex_optional_header(
    std::span<const std::byte> bytes, std::uint32_t guest_base, std::uint32_t key) {
    if (bytes.size() > max_xex_metadata || bytes.size() < 24 || guest_base % 4 != 0 ||
        static_cast<std::uint64_t>(guest_base) + bytes.size() > 0x100000000ull)
        throw XexError("invalid bounded guest header range");
    // This span is the complete header, while inspect_xex accepts a prefix.
    const auto header = inspect_xex(bytes, bytes.size() + 1ull);
    if (header.image_offset != bytes.size() || header.security_offset >= bytes.size())
        throw XexError("incomplete or inconsistent raw header span");
    std::unordered_set<std::uint32_t> keys;
    std::optional<std::uint32_t> result;
    const std::size_t table_end = 24 + header.optional.size() * 8;
    for (std::size_t i = 0; i < header.optional.size(); ++i) {
        const auto& entry = header.optional[i];
        if (!keys.insert(entry.key).second) throw XexError("duplicate optional header key");
        if (entry.key != key) continue;
        const auto kind = key & 255;
        if (kind == 0) {
            result = entry.value;
        } else if (kind == 1) {
            result = guest_base + static_cast<std::uint32_t>(28 + i * 8);
        } else {
            const std::size_t offset = entry.value;
            if (offset < table_end || offset % 4 || offset > bytes.size() || bytes.size() - offset < 4)
                throw XexError("optional payload offset outside header");
            const std::size_t length = kind == 255 ? be32(bytes, offset) : kind * 4;
            if (length < 4 || length > bytes.size() - offset)
                throw XexError("truncated optional payload");
            result = guest_base + entry.value;
        }
    }
    return result;
}
}
