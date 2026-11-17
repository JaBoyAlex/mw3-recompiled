// SPDX-License-Identifier: GPL-3.0-only
// Metadata-only adapter to the pinned MIT XenonUtils loader. No guest execution.
// Run only after tools/verify_inputs.py has matched the exact owned pair.
#include <image.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>

namespace {
void write_json_string(std::string_view value) {
    static constexpr char hex[] = "0123456789abcdef";
    std::cout << '"';
    for (const unsigned char c : value) {
        if (c == '"' || c == '\\') std::cout << '\\' << static_cast<char>(c);
        else if (c < 32 || c >= 127) std::cout << "\\u00" << hex[c >> 4] << hex[c & 15];
        else std::cout << static_cast<char>(c);
    }
    std::cout << '"';
}
}

int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "usage: mw3-image-probe <verified-owned.xex>\n"; return 2; }
    try {
        const auto size = std::filesystem::file_size(argv[1]);
        if (size < 24 || size > 64 * 1024 * 1024) throw std::runtime_error("input size outside analysis budget");
        std::vector<uint8_t> input(static_cast<std::size_t>(size));
        std::ifstream file(argv[1], std::ios::binary);
        if (!file.read(reinterpret_cast<char*>(input.data()), static_cast<std::streamsize>(size)))
            throw std::runtime_error("incomplete input read");
        const auto image = Image::ParseImage(input.data(), input.size());
        if (!image.data || image.sections.empty()) throw std::runtime_error("loader produced no image sections");
        // The upstream loader normalizes import thunks in its private in-memory image.
        // This reports metadata only; it does not dump that image or modify the input.
        std::cout << "{\n\"base\":" << image.base << ",\"size\":" << image.size
                  << ",\"entry_point\":" << image.entry_point << ",\"sections\":[";
        bool first = true;
        for (const auto& section : image.sections) {
            if (!first) std::cout << ',';
            first = false;
            std::cout << "{\"name\":";
            // PE section names are exactly eight bytes and need not be NUL terminated.
            // The upstream loader currently constructs a C string; restrict the report
            // to the field's real extent instead of propagating adjacent bytes.
            write_json_string(std::string_view(section.name).substr(0, 8));
            std::cout << ",\"address\":" << section.base
                      << ",\"size\":" << section.size << ",\"code\":" << ((section.flags & SectionFlags_Code) ? "true" : "false") << '}';
        }
        std::cout << "],\"resolved_import_symbols\":[";
        first = true;
        for (const auto& symbol : image.symbols) {
            if (!first) std::cout << ',';
            first = false;
            std::cout << "{\"name\":";
            write_json_string(symbol.name);
            std::cout << ",\"address\":" << symbol.address << '}';
        }
        std::cout << "],\"unknown_import_coverage\":\"not-established\",\"guest_executed\":false}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
