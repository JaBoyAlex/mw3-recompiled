// SPDX-License-Identifier: GPL-3.0-only
// Metadata-only adapter to the pinned MIT XenonUtils loader. No guest execution.
// Run only after tools/verify_inputs.py has matched the exact owned pair.
#include <image.h>
#include <disasm.h>
#include "scan.h"
#include "imports.h"
#include "switches.h"
#include "import_hook.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <vector>

namespace {
using namespace mw3::analysis;
std::optional<std::vector<ImportLibrary>> original_imports;
struct ExportName { const char* name; const char* kind; };
#define XE_EXPORT(MODULE, ORDINAL, NAME, TYPE) {ORDINAL, {#NAME, #TYPE}}
const std::map<uint32_t,ExportName> audit_xam_exports{
#include <xbox/xam_table.inc>
};
const std::map<uint32_t,ExportName> audit_kernel_exports{
#include <xbox/xboxkrnl_table.inc>
};
#undef XE_EXPORT
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

// Verify actual candidate words through the upstream table-driven disassembler,
// separately from our direct encoding comparison. No disassembly is emitted.
void verify_helper(const Region& region, uint32_t address, const HelperPattern& p) {
    const bool save=p.name.starts_with("save"), gpr=p.name.find("gpr")!=std::string::npos;
    const bool fpr=p.name.find("fpr")!=std::string::npos, extended=p.first==64;
    std::vector<std::pair<std::string,std::string>> expected;
    for (uint32_t reg=p.first; reg<=p.last; ++reg) {
        const auto number=std::to_string(reg);
        if (gpr || fpr) {
            expected.emplace_back(gpr ? (save ? "std" : "ld") : (save ? "stfd" : "lfd"),
                std::string(gpr ? "r" : "f")+number+","+std::to_string(-8*int((gpr ? 33 : 32)-reg))+
                (gpr ? "(r1)" : "(r12)"));
        } else {
            expected.emplace_back("li","r11,"+std::to_string(-16*int((extended ? 128 : 32)-reg)));
            expected.emplace_back(extended ? (save ? "stvx128" : "lvx128") : (save ? "stvx" : "lvx"),
                                  "v"+number+",r11,r12");
        }
    }
    if (gpr) {
        expected.emplace_back(save ? "stw" : "lwz", "r12,-8(r1)");
        if (!save) expected.emplace_back("mtlr","r12");
    }
    expected.emplace_back("blr", "");
    for (size_t i=0; i<expected.size(); ++i) {
        ppc_insn insn{};
        if (ppc::Disassemble(region.bytes.data()+address-region.base+i*4,4,address+i*4,insn)!=4 ||
            !insn.opcode || expected[i].first!=insn.opcode->name || expected[i].second!=insn.op_str)
            throw std::runtime_error("helper decoder disagrees with encoding/ABI scan: "+p.name);
    }
}

void write_analysis(const Image& image,const std::vector<std::pair<uint32_t,uint32_t>>& switches) {
    std::vector<Region> regions;
    const Section* pdata=nullptr;
    uint64_t code_bytes=0;
    for (const auto& s : image.sections) {
        if (s.base<image.base || uint64_t(s.base)-image.base+s.size>image.size)
            throw std::runtime_error("section outside loaded image");
        const bool code=bool(s.flags&SectionFlags_Code);
        if (code && (s.base%4 || s.size%4)) throw std::runtime_error("unaligned code section");
        regions.push_back({uint32_t(s.base),{s.data,s.size},code});
        if (code) code_bytes+=s.size;
        if (std::string_view(s.name).substr(0,8)==".pdata") pdata=&s;
    }
    if (!pdata) throw std::runtime_error("missing pdata");
    const auto functions=parse_pdata({pdata->data,pdata->size},regions);
    std::cout << ",\"helpers\":[";
    bool first=true;
    for (const auto& p : helper_patterns()) {
        if (!first) std::cout << ',';
        first=false;
        const auto hits=find_helper(regions,p);
        std::cout << "{\"family\":"; write_json_string(p.name);
        std::cout << ",\"first_register\":" << p.first << ",\"last_register\":" << p.last
                  << ",\"stride\":" << p.stride << ",\"size\":" << p.words.size()*4
                  << ",\"candidates\":[";
        bool hit_first=true;
        for (const auto address : hits) {
            for (const auto& r : regions) if (r.code && contains(r,address,p.words.size()*4)) verify_helper(r,address,p);
            if (!hit_first) std::cout << ',';
            hit_first=false;
            std::cout << address;
        }
        std::cout << "],\"decoder_checked\":true}";
    }
    std::cout << "],\"pdata\":{\"entries\":" << functions.functions.size()
              << ",\"zero_rows\":" << functions.zero_rows << ",\"overlaps\":" << functions.overlaps
              << ",\"covered_code_bytes\":" << functions.covered_bytes << ",\"code_bytes\":" << code_bytes
              << ",\"type_counts\":[";
    for (size_t i=0; i<4; ++i) { if (i) std::cout << ','; std::cout << functions.types[i]; }
    std::cout << "],\"functions\":[";
    first=true;
    for (const auto& f : functions.functions) {
        if (!first) std::cout << ',';
        first=false;
        std::cout << "{\"address\":" << f.begin << ",\"size\":" << f.length
                  << ",\"prologue\":" << f.prologue << ",\"type\":" << f.type << '}';
    }
    std::cout << "]},\"flow_scan\":{\"immediate_calls\":[";
    first=true;
    uint32_t returns=0;
    std::vector<std::pair<uint32_t,std::string>> indirect;
    for (const auto& r : regions) if (r.code) for (size_t off=0; off<r.bytes.size(); off+=4) {
        const auto word=be32(r.bytes,off), site=r.base+uint32_t(off);
        if ((word>>26)==18 && (word&1)) {
            const auto b=immediate_branch(site,word);
            if (!first) std::cout << ',';
            first=false;
            std::cout << "{\"site\":" << site << ",\"target\":" << b.target
                      << ",\"target_in_code\":" << (in_code(regions,b.target,4) ? "true" : "false") << '}';
        }
        if ((word>>26)==19) {
            const auto xo=(word>>1)&1023;
            if (word==0x4e800020) ++returns;
            else if (xo==16 || xo==528) indirect.emplace_back(site,xo==16 ? "lr" : "ctr");
        }
    }
    std::cout << "],\"canonical_blr_words\":" << returns << ",\"unresolved_indirect_sites\":[";
    first=true;
    for (const auto& [site,kind] : indirect) {
        if (!first) std::cout << ',';
        first=false;
        std::cout << "{\"site\":" << site << ",\"register\":"; write_json_string(kind); std::cout << '}';
    }
    std::cout << "],\"exception_paths_resolved\":false,\"scan_is_reachable_code_proof\":false}";
    std::cout << ",\"independent_switch_checks\":[";
    first=true;
    for (const auto& [base,count] : switches) {
        const auto checked=verify_absolute_switch(regions,base,count);
        if (!first) std::cout << ',';
        first=false;
        std::cout << "{\"base\":" << checked.base << ",\"r\":" << checked.index_register
                  << ",\"default\":" << checked.default_target << ",\"table_address\":" << checked.table_address
                  << ",\"comparison_address\":" << checked.comparison_address << ",\"guard_address\":" << checked.guard_address
                  << ",\"kind\":\"absolute-with-range-evidence\",\"dominance_proven\":false,\"labels\":[";
        for (size_t i=0;i<checked.labels.size();++i) { if (i) std::cout << ','; std::cout << checked.labels[i]; }
        std::cout << "]}";
    }
    std::cout << ']';
}

void write_imports() {
    if (!original_imports) throw std::runtime_error("pre-normalization observer did not run");
    std::cout << ",\"import_audit\":{\"observed_before_normalization\":true,\"runtime_implemented\":false,\"libraries\":[";
    bool first_lib=true;
    for (const auto& lib : *original_imports) {
        if (!first_lib) std::cout << ',';
        first_lib=false;
        std::cout << "{\"name\":"; write_json_string(lib.name);
        std::cout << ",\"id\":" << lib.id << ",\"version_raw\":" << lib.version
                  << ",\"minimum_version_raw\":" << lib.minimum_version << ",\"name_index_raw\":" << lib.name_index
                  << ",\"records\":[";
        const auto* exports=lib.name=="xam.xex" ? &audit_xam_exports : lib.name=="xboxkrnl.exe" ? &audit_kernel_exports : nullptr;
        bool first=true;
        for (const auto& r : lib.records) {
            if (!first) std::cout << ',';
            first=false;
            std::cout << "{\"address\":" << r.address << ",\"ordinal\":" << r.ordinal
                      << ",\"type\":" << r.type << ",\"hint\":" << r.hint << ",\"export_name\":";
            const auto* found=exports && exports->contains(r.ordinal) ? &exports->at(r.ordinal) : nullptr;
            if (found) write_json_string(found->name); else std::cout << "null";
            std::cout << ",\"export_kind\":";
            if (found) write_json_string(found->kind); else std::cout << "null";
            std::cout << '}';
        }
        std::cout << "]}";
    }
    std::cout << "]}";
}
}

void mw3_observe_imports(const Image& image,const uint8_t* input,std::size_t size) {
    if (original_imports) throw std::runtime_error("import observer invoked twice");
    auto imports=mw3::analysis::import_header({input,size});
    std::vector<mw3::analysis::Region> regions;
    for (const auto& s : image.sections) {
        if (s.base>UINT32_MAX || s.base<image.base || uint64_t(s.base)-image.base+s.size>image.size)
            throw std::runtime_error("import section outside image");
        regions.push_back({uint32_t(s.base),{s.data,s.size},bool(s.flags&SectionFlags_Code)});
    }
    mw3::analysis::read_import_records(imports,regions);
    original_imports=std::move(imports);
}

int main(int argc, char** argv) {
    if (argc<2 || argc>1026 || argc%2) { std::cerr << "usage: mw3-image-probe <verified-owned.xex> [switch-base case-count]...\n"; return 2; }
    try {
        std::vector<std::pair<uint32_t,uint32_t>> switches;
        auto number=[](const char* text) {
            size_t end=0; const auto value=std::stoull(text,&end,0);
            if (text[end] || value>UINT32_MAX) throw std::runtime_error("invalid switch argument");
            return uint32_t(value);
        };
        for (int i=2;i<argc;i+=2) switches.emplace_back(number(argv[i]),number(argv[i+1]));
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
        std::cout << ']';
        write_analysis(image,switches);
        write_imports();
        std::cout << ",\"unknown_import_coverage\":\"records-observed-runtime-unverified\",\"guest_executed\":false}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
