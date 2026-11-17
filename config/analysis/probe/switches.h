// SPDX-License-Identifier: GPL-3.0-only
// Independent, bounded verifier for guarded absolute PPC jump tables. This
// certifies supplied candidates; it is not another general switch analyzer.
#pragma once
#include "scan.h"
namespace mw3::analysis {
inline uint32_t mapped_word(std::span<const Region> regions,uint32_t address,bool code=false) {
    const Region* found=nullptr;
    for (const auto& r : regions) if ((!code || r.code) && contains(r,address,4)) {
        if (found) throw std::runtime_error("ambiguous mapped word");
        found=&r;
    }
    if (!found || address%4) throw std::runtime_error("unmapped/unaligned word");
    return be32(found->bytes,address-found->base);
}
struct AbsoluteSwitch { uint32_t base,index_register,default_target,table_address,comparison_address,guard_address; std::vector<uint32_t> labels; };
inline AbsoluteSwitch verify_absolute_switch(std::span<const Region> regions,uint32_t base,uint32_t count) {
    if (base<8 || !count || count>65536 || !in_code(regions,base,24))
        throw std::runtime_error("switch window/count outside budget");
    const auto hi=mapped_word(regions,base,true), lo=mapped_word(regions,base+4,true);
    const auto scale=mapped_word(regions,base+8,true), load=mapped_word(regions,base+12,true);
    const auto ctr=mapped_word(regions,base+16,true), branch=mapped_word(regions,base+20,true);
    const auto pointer=(hi>>21)&31, index=(scale>>21)&31, scaled=(scale>>16)&31, loaded=(load>>21)&31;
    // lis/addi pointer construction; rlwinm index*4; lwzx; mtctr; bctr.
    if ((hi>>26)!=15 || ((hi>>16)&31)!=0 || pointer==0 ||
        (lo>>26)!=14 || ((lo>>21)&31)!=pointer || ((lo>>16)&31)!=pointer ||
        (scale>>26)!=21 || ((scale>>11)&31)!=2 || ((scale>>6)&31)!=0 || ((scale>>1)&31)!=29 || (scale&1) ||
        (load>>26)!=31 || ((load>>1)&1023)!=23 || (load&1) ||
        !((((load>>16)&31)==pointer && ((load>>11)&31)==scaled) ||
          (scaled!=0 && ((load>>16)&31)==scaled && ((load>>11)&31)==pointer)) ||
        pointer==scaled ||
        (ctr>>26)!=31 || ((ctr>>1)&1023)!=467 || ((ctr>>21)&31)!=loaded || (ctr&1) ||
        ((((ctr>>16)&31)|(((ctr>>11)&31)<<5))!=9) || branch!=0x4e800420)
        throw std::runtime_error("unsupported absolute switch fields: pointer="+std::to_string(pointer)+
            " index="+std::to_string(index)+" scaled="+std::to_string(scaled)+
            " shift="+std::to_string((scale>>11)&31)+" mask="+std::to_string((scale>>6)&31)+":"+std::to_string((scale>>1)&31));
    // Locate the nearest unsigned-GT guard and its comparison within a bounded
    // compiler window. This is count/default evidence, not CFG dominance proof.
    uint32_t cmp=0,guard=0,cmp_address=0,guard_address=0;
    for (uint32_t back=4;back<=128 && back<=base;back+=4) {
        const auto address=base-back;
        if (!in_code(regions,address,4)) break;
        const auto word=mapped_word(regions,address,true);
        if (!guard_address) {
            if ((word>>26)==16 && ((((word>>21)&31)&~1u)==12) && ((word>>16)&3)==1 && !(word&3)) {
                guard=word; guard_address=address;
            }
        } else if ((word>>26)==10 && ((word>>23)&7)==((guard>>16)&31)/4) {
            cmp=word; cmp_address=address; break;
        }
    }
    if (!guard_address || !cmp_address || (cmp&0x00600000) || ((cmp>>16)&31)!=index || (cmp&65535)+1!=count)
        throw std::runtime_error("switch range guard disagrees");
    const auto low=lo&65535;
    const uint32_t table=((hi&65535)<<16)+uint32_t(low&0x8000 ? int64_t(low)-65536 : low);
    const auto delta=guard&0xfffc;
    const uint32_t fallback=uint32_t(int64_t(guard_address)+(delta&0x8000 ? int64_t(delta)-65536 : delta));
    if (!in_code(regions,fallback,4)) throw std::runtime_error("switch default outside code");
    AbsoluteSwitch result{base,index,fallback,table,cmp_address,guard_address,{}};
    const Region* table_region=nullptr;
    for (const auto& r : regions) if (contains(r,table,uint64_t(count)*4)) {
        if (table_region) throw std::runtime_error("ambiguous switch table region");
        table_region=&r;
    }
    if (!table_region || table%4) throw std::runtime_error("switch table outside mapped range");
    for (uint32_t i=0;i<count;++i) {
        const auto target=be32(table_region->bytes,table-table_region->base+size_t(i)*4);
        if (target%4 || !in_code(regions,target,4)) throw std::runtime_error("switch case outside code");
        result.labels.push_back(target);
    }
    return result;
}
} // namespace mw3::analysis
