// SPDX-License-Identifier: GPL-3.0-only
// Bounded metadata scans. Instruction encodings/ABI patterns are described in
// the pinned XenonRecomp README and PowerPC decoder; no title signatures here.
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace mw3::analysis {
struct Region { uint32_t base; std::span<const uint8_t> bytes; bool code; };
inline uint32_t be32(std::span<const uint8_t> bytes, size_t offset) {
    if (offset > bytes.size() || bytes.size() - offset < 4) throw std::runtime_error("truncated word");
    return uint32_t(bytes[offset]) << 24 | uint32_t(bytes[offset+1]) << 16 |
           uint32_t(bytes[offset+2]) << 8 | bytes[offset+3];
}
inline bool contains(const Region& r, uint64_t address, uint64_t size) {
    return address >= r.base && address <= uint64_t(r.base) + r.bytes.size() &&
           size <= uint64_t(r.base) + r.bytes.size() - address;
}
inline bool in_code(std::span<const Region> regions, uint64_t address, uint64_t size) {
    return std::any_of(regions.begin(), regions.end(), [&](auto& r) { return r.code && contains(r,address,size); });
}
struct HelperPattern {
    std::string name;
    uint32_t first, last, stride;
    std::vector<uint32_t> words;
};
// Generate entire ladders including their LR/return tails, never prefix-only hits.
inline std::vector<HelperPattern> helper_patterns() {
    std::vector<HelperPattern> result;
    for (unsigned family=0; family<4; ++family) for (unsigned save=0; save<2; ++save) {
        const bool vector = family >= 2, extended = family == 3;
        const uint32_t first=extended ? 64 : 14, last=extended ? 127 : 31;
        std::string name=save ? "save" : "rest";
        name += family==0 ? "gprlr_14" : family==1 ? "fpr_14" : extended ? "vmx_64" : "vmx_14";
        HelperPattern p{name,first,last,vector ? 8u : 4u,{}};
        for (uint32_t reg=first; reg<=last; ++reg) {
            if (!vector) {
                const uint32_t op=family==0 ? (save ? 62 : 58) : (save ? 54 : 50);
                const uint32_t base=family==0 ? 1 : 12;
                const int offset=-8*int((family==0 ? 33 : 32)-reg);
                p.words.push_back(op<<26 | reg<<21 | base<<16 | (uint32_t(offset)&0xffff));
            } else {
                const int offset=-16*int((extended ? 128 : 32)-reg);
                p.words.push_back(14u<<26 | 11u<<21 | (uint32_t(offset)&0xffff)); // li r11,offset
                if (extended)
                    p.words.push_back(4u<<26 | (reg&31)<<21 | 11u<<16 | 12u<<11 |
                                      ((reg&96)>>3) | (save ? 451u : 195u));
                else
                    p.words.push_back(31u<<26 | reg<<21 | 11u<<16 | 12u<<11 | (save ? 231u : 103u)<<1);
            }
        }
        if (family==0) {
            p.words.push_back((save ? 36u : 32u)<<26 | 12u<<21 | 1u<<16 | 0xfff8);
            if (!save) p.words.push_back(0x7d8803a6); // mtlr r12
        }
        p.words.push_back(0x4e800020); // blr
        result.push_back(std::move(p));
    }
    return result;
}
inline std::vector<uint32_t> find_helper(std::span<const Region> regions, const HelperPattern& p) {
    std::vector<uint32_t> hits;
    const size_t length=p.words.size()*4;
    for (const auto& r : regions) {
        if (!r.code || r.bytes.size()<length) continue;
        for (size_t off=0; off<=r.bytes.size()-length; off+=4) {
            if ((uint64_t(r.base)+off)%4) continue;
            if (be32(r.bytes,off)!=p.words.front()) continue;
            bool match=true;
            for (size_t i=1; i<p.words.size(); ++i)
                if (be32(r.bytes,off+i*4)!=p.words[i]) { match=false; break; }
            if (match) hits.push_back(r.base+uint32_t(off));
        }
    }
    return hits; // Preserve ambiguity; never silently choose the first match.
}
struct RuntimeFunction { uint32_t begin, length, prologue, type; };
struct Pdata {
    std::vector<RuntimeFunction> functions;
    uint32_t zero_rows=0, overlaps=0;
    uint64_t covered_bytes=0;
    std::array<uint32_t,4> types{};
};
inline Pdata parse_pdata(std::span<const uint8_t> bytes, std::span<const Region> regions) {
    if (bytes.size()%8) throw std::runtime_error("partial pdata row");
    Pdata result;
    uint32_t previous=0;
    bool have_previous=false;
    uint64_t covered_end=0;
    for (size_t off=0; off<bytes.size(); off+=8) {
        const uint32_t begin=be32(bytes,off), word=be32(bytes,off+4);
        if (begin==0 && word==0) { ++result.zero_rows; continue; }
        const uint32_t length=((word>>8)&0x3fffff)*4, prologue=(word&255)*4, type=word>>30;
        if (begin%4 || !length || prologue>length || !in_code(regions,begin,length))
            throw std::runtime_error("invalid pdata range/prologue");
        if (have_previous && begin<previous) throw std::runtime_error("unsorted pdata");
        const uint64_t end=uint64_t(begin)+length;
        if (begin<covered_end) ++result.overlaps;
        result.covered_bytes += end>covered_end ? end-std::max<uint64_t>(begin,covered_end) : 0;
        covered_end=std::max(covered_end,end);
        previous=begin; have_previous=true;
        ++result.types[type];
        result.functions.push_back({begin,length,prologue,type});
    }
    return result;
}
struct Branch { uint32_t site, target; bool link, absolute; };
inline Branch immediate_branch(uint32_t site, uint32_t word) {
    if ((word>>26)!=18) throw std::runtime_error("not immediate branch");
    const uint32_t displacement=word&0x03fffffc;
    const int64_t signed_disp=(displacement&0x02000000) ? int64_t(displacement)-0x04000000 : displacement;
    return {site, uint32_t((word&2 ? int64_t(0) : int64_t(site))+signed_disp), bool(word&1), bool(word&2)};
}
} // namespace mw3::analysis
