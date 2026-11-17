// SPDX-License-Identifier: GPL-3.0-only
#include "mw3/xex.hpp"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string_view>

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--version") {
        std::cout << "mw3-xex-inspect 0.1.0 (metadata only; no game runtime)\n";
        return 0;
    }
    if (argc != 2) { std::cerr << "usage: mw3-xex-inspect <owned-file.xex>\n"; return 2; }
    try {
        const auto path = std::filesystem::path(argv[1]);
        if (!std::filesystem::is_regular_file(path)) throw mw3::XexError("expected a regular file");
        const auto size = std::filesystem::file_size(path);
        const auto amount = static_cast<std::size_t>(std::min<std::uintmax_t>(size, mw3::max_xex_metadata));
        std::vector<std::byte> bytes(amount);
        std::ifstream input(path, std::ios::binary);
        if (!input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(amount)))
            throw mw3::XexError("could not read file prefix");
        const auto header = mw3::inspect_xex(bytes, size);
        std::cout << "XEX2 metadata; not a supported-build or ownership verification\n"
                  << "module_flags=0x" << std::hex << header.module_flags
                  << "\nimage_offset=0x" << header.image_offset
                  << "\nsecurity_offset=0x" << header.security_offset
                  << "\noptional_headers=" << std::dec << header.optional.size() << '\n';
        for (const auto& item : header.optional)
            std::cout << "key=0x" << std::hex << item.key << " value=0x" << item.value << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
