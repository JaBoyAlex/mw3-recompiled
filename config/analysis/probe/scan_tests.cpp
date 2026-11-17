// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic instructions/metadata only. Does not load an XEX.
#include "scan.h"
#include "imports.h"
#include "switches.h"
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
void import_tests() {
    // Original minimal header: two libraries deliberately name strings out of
    // order; the first library includes declared padding beyond its records.
    std::vector<uint8_t> input(156);
    auto put=[&](size_t offset,uint32_t value) { for (int i=0;i<4;++i) input.at(offset+i)=uint8_t(value>>(24-8*i)); };
    put(0,0x58455832); put(8,156); put(20,1); put(24,0x103ff); put(28,32);
    put(32,124); put(36,16); put(40,2);
    const std::array<uint8_t,16> names{'s','e','c','o','n','d','.','x','e','x',0,0,'a',0,0,0};
    std::copy(names.begin(),names.end(),input.begin()+44);
    put(60,52); put(84,3); put(88,0x10000001); put(92,0x10000000);
    put(96,0x00010002); put(100,0x1000); put(104,0x1010); // name 1, two records
    put(112,44); put(148,1); put(152,0x2000); // name 0, one record
    const auto pristine=input;
    auto libs=import_header(input);
    check(libs.size()==2 && libs[0].name=="a" && libs[1].name=="second.xex");
    check(libs[0].version==0x10000001 && libs[0].minimum_version==0x10000000);
    check(libs[1].addresses==std::vector<uint32_t>{0x2000});
    std::vector<uint8_t> text(32),data(4);
    auto store=[](std::vector<uint8_t>& bytes,size_t off,uint32_t value) {
        for (int i=0;i<4;++i) bytes.at(off+i)=uint8_t(value>>(24-8*i));
    };
    store(text,0,0x00000003); store(text,16,0x01000003); store(data,0,0x00010007);
    const std::array regions{Region{0x1000,text,true},Region{0x2000,data,false}};
    read_import_records(libs,regions);
    check(libs[0].records[0].ordinal==3 && libs[0].records[0].type==0);
    check(libs[0].records[1].ordinal==3 && libs[0].records[1].type==1);
    check(libs[1].records[0].hint==1 && libs[1].records[0].ordinal==7);
    check(input==pristine); // Header and record readers never write to inputs.
    store(data,0,0x02010007); read_import_records(libs,regions);
    check(libs[1].records[0].type==2); // Unknown kinds remain explicit, not dropped.
    store(data,0,0x01010007); refuses([&]{read_import_records(libs,regions);}); // thunk in data
    const std::array short_code{Region{0x1000,std::span(text).first(20),true},regions[1]};
    refuses([&]{read_import_records(libs,short_code);});
    const std::array missing{regions[0]}; refuses([&]{read_import_records(libs,missing);});
    const std::array overlap{regions[0],regions[0],regions[1]}; refuses([&]{read_import_records(libs,overlap);});
    for (size_t n=0;n<input.size();++n) refuses([&]{import_header(std::span(input).first(n));});
    const std::array mutations{
        std::pair{0u,0u}, std::pair{8u,155u}, std::pair{20u,4097u}, std::pair{24u,0u},
        std::pair{28u,0u}, std::pair{28u,155u}, std::pair{32u,11u}, std::pair{36u,UINT32_MAX},
        std::pair{40u,257u}, std::pair{40u,3u}, std::pair{60u,39u}, std::pair{60u,UINT32_MAX},
        std::pair{96u,0x00020002u}, std::pair{96u,0x0001ffffu}, std::pair{100u,0x1001u},
        std::pair{100u,0u}, std::pair{104u,0x1000u}, std::pair{112u,UINT32_MAX}};
    for (const auto& [offset,value] : mutations) { put(offset,value); refuses([&]{import_header(input);}); input=pristine; }
    input.insert(input.end(),0); put(8,157); put(32,125);
    refuses([&]{import_header(input);}); input=pristine;
    std::fill(input.begin()+44,input.begin()+60,0xff);
    refuses([&]{import_header(input);});
}
void switch_tests() {
    // Original PPC fixture: cmplwi r3,1; bgt default; lis/addi r11,0x2000;
    // slwi r10,r3,2; lwzx r11,r11,r10; mtctr r11; bctr; case/default BLRs.
    std::vector<uint8_t> code,table;
    for (const auto value : {0x28030001u,0x41810024u,0x3d600000u,0x396b2000u,0x546a103au,0x7d6b502eu,
                            0x7d6903a6u,0x4e800420u,0x4e800020u,0x4e800020u,0x4e800020u}) word(code,value);
    word(table,0x1020); word(table,0x1024);
    auto verify=[&](uint32_t base=0x1008,uint32_t count=2) {
        return verify_absolute_switch(std::array{Region{0x1000,code,true},Region{0x2000,table,false}},base,count);
    };
    const auto valid=verify();
    check(valid.index_register==3 && valid.table_address==0x2000 && valid.default_target==0x1028);
    check(valid.labels==std::vector<uint32_t>({0x1020,0x1024}));
    // r0 is a valid index in RB; only RA=0 has the literal-zero meaning.
    const auto original=code;
    code[17]=0x60; // rlwinm r0,r3,2,0,29
    code[21]=0x6b; code[22]=0x00; // lwzx r11,r11,r0
    check(verify().labels==valid.labels);
    code[21]=0x60; code[22]=0x58; // lwzx r11,r0,r11: RA=0 cannot index via r0
    refuses([&]{verify();}); code=original;
    refuses([&]{verify(4);}); refuses([&]{verify(0x1008,0);}); refuses([&]{verify(0x1008,65537);});
    refuses([&]{verify(0x1008,3);});
    // Corrupt each instruction, including the guard, data-flow links and bctr.
    for (size_t i=0;i<32;i+=4) { code[i+3]^=1; refuses([&]{verify();}); code[i+3]^=1; }
    for (size_t n=0;n<32;++n)
        refuses([&]{verify_absolute_switch(std::array{Region{0x1000,std::span(code).first(n),true},Region{0x2000,table,false}},0x1008,2);});
    for (size_t n=0;n<table.size();++n)
        refuses([&]{verify_absolute_switch(std::array{Region{0x1000,code,true},Region{0x2000,std::span(table).first(n),false}},0x1008,2);});
    table[3]^=1; refuses([&]{verify();}); table[3]^=1; // unaligned target
    table[0]=0xff; refuses([&]{verify();}); table[0]=0;
    refuses([&]{verify_absolute_switch(std::array{Region{0x1000,code,false},Region{0x2000,table,false}},0x1008,2);});
    code.insert(code.begin()+4,4,0); code[4]=0x60; // NOP between comparison and guard
    const auto separated=verify(0x100c);
    check(separated.comparison_address==0x1000 && separated.guard_address==0x1008 && separated.default_target==0x102c);
}
}
int main(int argc,char** argv) {
    try {
        if (argc==2) fixture(argv[1]); else if (argc==1) { synthetic(); import_tests(); switch_tests(); } else return 2;
        std::cout << "PASS: " << checks << " metadata scan checks (synthetic only)\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
