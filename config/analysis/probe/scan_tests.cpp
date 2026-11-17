// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic instructions/metadata only. Does not load an XEX.
#include "scan.h"
#include <fstream>
#include <iostream>
#include <iterator>

using namespace mw3::analysis;
namespace {
unsigned checks=0;
void check(bool ok) { ++checks; if (!ok) throw std::runtime_error("scan assertion "+std::to_string(checks)); }
void word(std::vector<uint8_t>& out, uint32_t value) {
    for (int shift=24; shift>=0; shift-=8) out.push_back(uint8_t(value>>shift));
}
template<class F> void refuses(F action) {
    bool refused=false;
    try { action(); } catch (const std::runtime_error&) { refused=true; }
    check(refused);
}
void fixture(const char* path) {
    std::ifstream file(path,std::ios::binary);
    if (!file) throw std::runtime_error("fixture not found");
    const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(file),{}};
    const std::array regions{Region{0x1000,bytes,true}};
    for (const auto& p : helper_patterns()) {
        const auto hits=find_helper(regions,p);
        check(hits.size()==(p.first==64 ? 0 : 1));
    }
}
void synthetic() {
    for (const auto& p : helper_patterns()) {
        std::vector<uint8_t> bytes;
        for (const auto w : p.words) word(bytes,w);
        auto scan=[&](bool code=true, uint32_t base=0x1000) {
            return find_helper(std::array{Region{base,bytes,code}},p);
        };
        check(scan()==std::vector<uint32_t>{0x1000});
        check(scan(false).empty());
        check(scan(true,0x1001).empty());
        for (size_t i=0; i<bytes.size(); ++i) {
            const std::array regions{Region{0x1000,std::span(bytes).first(i),true}};
            check(find_helper(regions,p).empty());
        }
        for (size_t i=0; i<bytes.size(); i+=4) {
            bytes[i+3]^=1; check(scan().empty()); bytes[i+3]^=1;
        }
        const auto copy=bytes;
        bytes.insert(bytes.end(),copy.begin(),copy.end());
        check(scan()==std::vector<uint32_t>({0x1000,0x1000+uint32_t(copy.size())}));
        // Two individually truncated sections must not become one helper.
        const auto half=copy.size()/8*4;
        const std::array split{Region{0x1000,std::span(copy).first(half),true},
                              Region{0x1000+uint32_t(half),std::span(copy).subspan(half),true}};
        check(find_helper(split,p).empty());
    }
    std::vector<uint8_t> code(0x100), pdata;
    const std::array regions{Region{0x1000,code,true},Region{0x2000,code,false}};
    // Overlapping suffix metadata is valid; union coverage must not double count.
    word(pdata,0x1000); word(pdata,(1u<<30)|(8u<<8)|2u);
    word(pdata,0x1010); word(pdata,(2u<<30)|(4u<<8));
    word(pdata,0); word(pdata,0);
    const auto parsed=parse_pdata(pdata,regions);
    check(parsed.functions.size()==2 && parsed.overlaps==1 && parsed.covered_bytes==32 && parsed.zero_rows==1);
    check(parsed.types[1]==1 && parsed.types[2]==1 && parsed.functions[0].prologue==8);
    pdata.push_back(0); refuses([&]{parse_pdata(pdata,regions);}); pdata.pop_back();
    for (const auto begin : {0x1001u,0x1100u,0x2000u,0xfffffffcu}) {
        std::vector<uint8_t> bad; word(bad,begin); word(bad,(1u<<30)|(4u<<8));
        refuses([&]{parse_pdata(bad,regions);});
    }
    for (const auto data : {1u<<30,(1u<<30)|(4u<<8)|5u,(1u<<30)|(0x3fffffu<<8)}) {
        std::vector<uint8_t> bad; word(bad,0x1000); word(bad,data);
        refuses([&]{parse_pdata(bad,regions);});
    }
    std::vector<uint8_t> unsorted;
    word(unsorted,0x1010); word(unsorted,0x40000100); word(unsorted,0x1000); word(unsorted,0x40000100);
    refuses([&]{parse_pdata(unsorted,regions);});
    const std::array<Region,1> high{Region{0xffffff00,code,true}};
    check(in_code(high,0xfffffffc,4)); check(!in_code(high,0xfffffffc,8));
    check(immediate_branch(0x1000,0x4bfffffd).target==0xffc); // bl -4
    check(immediate_branch(0x1000,0x48000007).target==4); // bla 4
    check(immediate_branch(0xfffffffc,0x48000005).target==0); // 32-bit wrap
    check(immediate_branch(0x1000,0x4a000001).target==0xfe001000); // min negative LI
    refuses([&]{immediate_branch(0,0x4e800020);});
    refuses([&]{be32(std::span(code).first(3),0);});
    refuses([&]{be32(code,SIZE_MAX);});
}
}
int main(int argc,char** argv) {
    try {
        if (argc==2) fixture(argv[1]); else if (argc==1) synthetic(); else return 2;
        std::cout << "PASS: " << checks << " metadata scan checks (synthetic only)\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
