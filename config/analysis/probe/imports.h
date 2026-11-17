// SPDX-License-Identifier: GPL-3.0-only
// Original bounded reader for the import header/record layouts described by the
// pinned XenonRecomp and ReXGlue sources. No cryptography or title bytes here.
#pragma once
#include "scan.h"
#include <set>

namespace mw3::analysis {
struct ImportRecord { uint32_t address, ordinal, type, hint; };
struct ImportLibrary {
    std::string name;
    uint32_t id, version, minimum_version, name_index;
    std::vector<uint32_t> addresses;
    std::vector<ImportRecord> records;
};
inline uint32_t be16(std::span<const uint8_t> bytes, size_t offset) {
    if (offset>bytes.size() || bytes.size()-offset<2) throw std::runtime_error("truncated halfword");
    return uint32_t(bytes[offset])<<8 | bytes[offset+1];
}
inline std::vector<ImportLibrary> import_header(std::span<const uint8_t> input) {
    if (input.size()<24 || be32(input,0)!=0x58455832) throw std::runtime_error("invalid XEX import input");
    const auto header_size=be32(input,8), count=be32(input,20);
    if (header_size>input.size() || count>4096 || uint64_t(24)+uint64_t(count)*8>header_size)
        throw std::runtime_error("invalid optional header extent");
    uint32_t offset=0;
    for (size_t i=0; i<count; ++i) if (be32(input,24+i*8)==0x000103ff) {
        if (offset) throw std::runtime_error("duplicate import header");
        offset=be32(input,28+i*8);
        if (offset<uint64_t(24)+uint64_t(count)*8 || uint64_t(offset)+12>header_size)
            throw std::runtime_error("invalid import header offset");
    }
    if (!offset) throw std::runtime_error("missing import header");
    const auto total=be32(input,offset), strings_size=be32(input,offset+4), libraries=be32(input,offset+8);
    if (total<12 || uint64_t(offset)+total>header_size || strings_size>total-12 || !libraries || libraries>256)
        throw std::runtime_error("invalid import block extent/count");
    const auto block=input.subspan(offset,total), strings=block.subspan(12,strings_size);
    std::vector<std::string> names;
    for (size_t pos=0; pos<strings.size();) {
        size_t end=pos;
        while (end<strings.size() && strings[end]) ++end;
        if (end==strings.size()) throw std::runtime_error("unterminated import name");
        if (end>pos && strings[pos]!=0xcd) {
            if (end-pos>255) throw std::runtime_error("import name exceeds budget");
            names.emplace_back(reinterpret_cast<const char*>(strings.data()+pos),end-pos);
        }
        pos=(end+1+3)&~size_t(3);
        if (pos>strings.size()) throw std::runtime_error("import string padding outside table");
    }
    size_t cursor=12+strings_size;
    std::set<uint32_t> all_addresses;
    std::vector<ImportLibrary> result;
    for (uint32_t i=0; i<libraries; ++i) {
        if (cursor>block.size() || block.size()-cursor<40) throw std::runtime_error("truncated import library");
        const auto size=be32(block,cursor), records=be16(block,cursor+38), index=be16(block,cursor+36);
        if (size<40 || size>block.size()-cursor || uint64_t(40)+uint64_t(records)*4>size || (index&255)>=names.size())
            throw std::runtime_error("invalid import library extent/name");
        ImportLibrary lib{names[index&255],be32(block,cursor+24),be32(block,cursor+28),be32(block,cursor+32),index,{},{}};
        for (size_t n=0; n<records; ++n) {
            const auto address=be32(block,cursor+40+n*4);
            if (address%4 || !address || !all_addresses.insert(address).second)
                throw std::runtime_error("invalid/duplicate import record address");
            lib.addresses.push_back(address);
        }
        result.push_back(std::move(lib));
        cursor+=size; // Respect declared size, including padding, not inferred record length.
    }
    if (cursor!=block.size()) throw std::runtime_error("unaccounted import block bytes");
    return result;
}
inline void read_import_records(std::vector<ImportLibrary>& libraries, std::span<const Region> regions) {
    for (auto& lib : libraries) {
        lib.records.clear();
        for (const auto address : lib.addresses) {
            const Region* region=nullptr;
            for (const auto& r : regions) if (contains(r,address,4)) {
                if (region) throw std::runtime_error("ambiguous import record region");
                region=&r;
            }
            if (!region) throw std::runtime_error("import record outside mapped sections");
            const auto value=be32(region->bytes,address-region->base);
            const auto type=value>>24;
            if (type==1 && (!region->code || !contains(*region,address,16)))
                throw std::runtime_error("function import thunk outside code");
            lib.records.push_back({address,value&0xffff,type,(value>>16)&255});
        }
    }
}
} // namespace mw3::analysis
