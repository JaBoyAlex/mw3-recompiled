// SPDX-License-Identifier: GPL-3.0-only
// Executes actual emitted PPC functions; no host implementation of the fixtures.
#include "ppc_config.h"
#include "dispatch.h"
#include <rex/kernel/heap.h>
#include <nlohmann/json.hpp>
#include <array>
#include <fstream>
#include <iostream>
#include <stdexcept>
using Json = nlohmann::json;

std::uint64_t read_register(PPCContext& ctx, const std::string& key) {
#include "read_register.inc"
  throw std::runtime_error("unsupported result register: " + key);
}
void write_register(PPCContext& ctx, const std::string& key, std::uint64_t value) {
#include "write_register.inc"
  throw std::runtime_error("unsupported input register: " + key);
}
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("expected private case file");
    std::ifstream stream(argv[1]);
    const auto cases = Json::parse(stream);
    rex::kernel::GuestAddressSpace memory;
    if (!memory.Initialize() || !memory.InitializeFunctionTable(REX_CODE_BASE, REX_CODE_SIZE, REX_IMAGE_BASE, REX_IMAGE_SIZE))
      throw std::runtime_error("cannot initialize synthetic memory");
    auto* heap = memory.LookupHeap(0x10000);
    if (!heap || !heap->AllocFixed(0x10000, 0x20000, 0x1000,
            rex::kernel::kMemoryAllocationReserve | rex::kernel::kMemoryAllocationCommit,
            rex::kernel::kMemoryProtectRead | rex::kernel::kMemoryProtectWrite))
      throw std::runtime_error("cannot commit synthetic memory");
    register_functions(memory);
    const auto original_csr=rex::ppc::FPSCRPlatform::GetCSR();
    const auto case_csr=(original_csr & ~static_cast<u32>(rex::ppc::FPSCRPlatform::kRoundMaskVal | rex::ppc::FPSCRPlatform::kFlushMask))
        | rex::ppc::FPSCRPlatform::kExceptionsMasked;
    std::size_t failures = 0;
    for (const auto& entry : cases) {
      PPCContext ctx{};
      rex::ppc::FPSCRPlatform::SetCSR(case_csr);
      ctx.fpscr.LoadFromHost();
      ctx.r1.u64 = 0x28000;
      ctx.r6.u64 = 0x10000;
      ctx.r31.u64 = 0x1122334455667788ull;
      std::memset(memory.GetVirtualMembase() + 0x10000, 0xa5, 0x20000);
      for (const auto& [key, value] : entry.at("in").items()) write_register(ctx, key, value.get<std::uint64_t>());
      dispatch(entry.at("function"), ctx, memory.GetVirtualMembase());
      Json mismatches = Json::array();
      for (const auto& [key, expected] : entry.at("out").items()) {
        const auto actual = key.starts_with("mem")
            ? static_cast<std::uint64_t>(memory.GetVirtualMembase()[0x10000 + std::stoul(key.substr(3))])
            : read_register(ctx, key);
        const auto value = expected.is_object() ? expected.at("value").get<std::uint64_t>() : expected.get<std::uint64_t>();
        const auto mask = expected.is_object() ? expected.at("mask").get<std::uint64_t>() : ~std::uint64_t{0};
        if ((actual & mask) != (value & mask)) mismatches.push_back({{"register", key}, {"expected", expected}, {"actual", actual}});
      }
      if (!mismatches.empty()) ++failures;
      std::cout << Json({{"id", entry.at("id")}, {"status", mismatches.empty() ? "PASS" : "FAIL"}, {"mismatches", mismatches}}).dump() << '\n';
    }
    std::cout << Json({{"completed", cases.size()}, {"failures", failures}}).dump() << std::endl;
    rex::ppc::FPSCRPlatform::SetCSR(original_csr);
    return failures ? 1 : 0;
  } catch (const std::exception& e) {
    std::cerr << "PPC_ORACLE_ERROR: " << e.what() << std::endl;
    return 2;
  }
}
