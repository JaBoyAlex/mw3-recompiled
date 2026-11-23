// SPDX-License-Identifier: GPL-3.0-only
// Maintained host diagnostics; original title instructions remain private.
u32 startup_reserved = 0;
u32 startup_frame = 0;
bool startup_inspected = false, startup_committed = false, startup_heap_checked = false;

void StartupResumeFirst(PPCContext& ctx, u32 address, const char* nonce) {
  Require(ctx.r22.u32 == MW3_STARTUP_GLOBAL_BASE &&
          LoadRawWord(MW3_STARTUP_GLOBAL_ADDRESS) == MW3_STARTUP_GLOBAL_VALUE,
          "startup owned-data identity mismatch");
  Require(ctx.r30.u32 == 65536 && u64(ctx.r31.u32) + 344 <= 0x100000000ull,
          "startup frame/page setup mismatch");
  auto& memory = current->GetGuestMemory();
  Require(bool(memory.GetReadOnlySpan(ctx.r31.u32 + 332, 4)) &&
          bool(memory.GetWritableSpan(ctx.r31.u32 + 332, 4)), "startup size word is not read/write");
  startup_reserved = address;
  startup_frame = ctx.r31.u32;
#ifdef MW3_STARTUP_EXECUTE
  Require(LoadRawWord(ctx.r31.u32 + 332) == MW3_STARTUP_HINT && ctx.r23.u32 == MW3_STARTUP_FLAGS &&
          ctx.r24.u32 == MW3_STARTUP_EXTRA && ctx.r25.u32 == MW3_STARTUP_FIELD && ctx.r21.u32 == 0,
          "startup captured context mismatch");
#endif
  std::fprintf(stderr, "MW3_STARTUP_RESUME:reserved=%08x hint=%08x page=%08x flags=%08x extra=%08x field=%08x global=%08x value=%08x nonce=%s\n",
               address, LoadRawWord(ctx.r31.u32 + 332), ctx.r30.u32, ctx.r23.u32, ctx.r24.u32,
               ctx.r25.u32, u32(MW3_STARTUP_GLOBAL_ADDRESS), LoadRawWord(MW3_STARTUP_GLOBAL_ADDRESS), nonce);
}

void StartupInspectCommit(PPCContext& ctx) {
  const char* nonce = std::getenv("MW3_ALLOCATION_NONCE");
  Require(nonce && std::strlen(nonce) == 32, "startup nonce missing");
  Require(++allocation_inputs == 2 && allocation_checked && startup_reserved,
          "startup call budget/order mismatch");
  if (mode == "startup-bad-caller" || mode == "startup-bad-pointer" || mode == "startup-bad-value") {
    std::fprintf(stderr, "MW3_STARTUP_MUTATION:%s nonce=%s\n", mode.c_str(), nonce);
    if (mode == "startup-bad-caller") ctx.lr ^= 4;
    if (mode == "startup-bad-pointer") ctx.r3.u32 ^= 1;
    if (mode == "startup-bad-value") ctx.r5.u32 ^= 0x2000;
  }
  Require(ctx.lr == MW3_STARTUP_COMMIT_LR, "startup commit caller mismatch");
  Require(ctx.r31.u32 == startup_frame && u64(ctx.r31.u32) + 344 <= 0x100000000ull && ctx.r3.u32 == ctx.r31.u32 + 84 &&
          ctx.r4.u32 == ctx.r31.u32 + 332, "startup commit pointer setup mismatch");
  Require(ctx.r5.u32 == 0x60001000 && ctx.r6.u32 == 4 && ctx.r7.u32 == 0 &&
          ctx.r7.u32 == ctx.r27.u32, "startup commit value setup mismatch");
  auto& memory = current->GetGuestMemory();
  for (u32 address : {ctx.r3.u32, ctx.r4.u32})
    Require(!(address & 3u) && bool(memory.GetReadOnlySpan(address, 4)) &&
            bool(memory.GetWritableSpan(address, 4)), "startup commit word is not read/write");
  const u32 address = LoadRawWord(ctx.r3.u32), size = LoadRawWord(ctx.r4.u32);
  Require(address == startup_reserved && size && size <= MW3_STARTUP_LIMIT && size <= 0x100000 &&
          u64(address) + ((u64(size) + 65535) & ~u64{65535}) <= u64(startup_reserved) + 0x100000,
          "startup commit request exceeds reservation/budget");
  Require(ctx.r22.u32 == MW3_STARTUP_GLOBAL_BASE &&
          LoadRawWord(MW3_STARTUP_GLOBAL_ADDRESS) == MW3_STARTUP_GLOBAL_VALUE,
          "startup owned-data changed before commit");
  std::fprintf(stderr, "MW3_STARTUP_INPUT:lr=%08x r31=%08x base_word=%08x size_word=%08x base=%08x size=%08x type=%08x protect=%08x region=%08x nonce=%s\n",
               u32(ctx.lr), ctx.r31.u32, ctx.r3.u32, ctx.r4.u32, address, size,
               ctx.r5.u32, ctx.r6.u32, ctx.r7.u32, nonce);
  startup_inspected = true;
#ifdef MW3_STARTUP_EXECUTE
  Require(size == MW3_STARTUP_SIZE, "startup captured commit size mismatch");
  const u32 base_word = ctx.r3.u32, size_word = ctx.r4.u32;
  std::array<std::byte, 12> base_before{}, size_before{}, after{};
  Require(bool(memory.CopyFrom(base_word - 4, base_before)) && bool(memory.CopyFrom(size_word - 4, size_before)),
          "startup neighbour snapshot failed");
  auto& space = k::GetAddressSpace(*current);
  const auto pages = space.GetTitlePages();
  std::fprintf(stderr, "MW3_STARTUP_COMMIT_CALL:nonce=%s\n", nonce);
  original_allocation(ctx, static_cast<u8*>(current->GetMembase().GetBase()));
  const u32 result_base = LoadRawWord(base_word), result_size = LoadRawWord(size_word);
  std::fprintf(stderr, "MW3_STARTUP_COMMIT_RETURN:status=%08x base=%08x size=%08x nonce=%s\n",
               ctx.r3.u32, result_base, result_size, nonce);
  Require(ctx.r3.u32 == 0, "startup commit SDK status mismatch");
  auto* heap = space.LookupHeap(address);
  k::HeapAllocation head{}, last{}, tail{};
  const u32 state = k::kMemoryAllocationReserve | k::kMemoryAllocationCommit;
  const u32 protect = k::kMemoryProtectRead | k::kMemoryProtectWrite;
  Require(result_base == address && result_size == size && heap &&
          heap->GetHeapType() == k::HeapType::kGuestVirtual && heap->GetPageSize() == 65536 &&
          heap->QueryRegionInfo(address, &head) && head.allocation_base == address &&
          head.allocation_size == 0x100000 && head.region_size == size && head.state == state && head.protect == protect &&
          heap->QueryRegionInfo(address + size - 1, &last) && last.allocation_base == address &&
          last.allocation_size == 0x100000 && last.state == state && last.protect == protect &&
          heap->QueryRegionInfo(address + size, &tail) && tail.allocation_base == address &&
          tail.allocation_size == 0x100000 && tail.state == k::kMemoryAllocationReserve &&
          bool(memory.GetReadOnlySpan(address, size)) && bool(memory.GetWritableSpan(address, size)) &&
          !memory.GetReadOnlySpan(address + size, 4) && !memory.GetWritableSpan(address + size, 4) &&
          !memory.GetReadOnlySpan(address + 0xffffc, 4) && !memory.GetWritableSpan(address + 0xffffc, 4) &&
          space.GetTitlePages() == pages + size / 4096, "startup commit geometry/access/accounting mismatch");
  auto committed = memory.GetReadOnlySpan(address, size);
  Require(bool(committed), "startup committed span missing");
  for (auto byte : *committed) Require(byte == std::byte{0}, "startup fresh commitment is not zero");
  for (auto pair : {std::pair{base_word, &base_before}, std::pair{size_word, &size_before}}) {
    Require(bool(memory.CopyFrom(pair.first - 4, after)), "startup neighbour recheck failed");
    for (unsigned i = 0; i < 12; ++i)
      if (i < 4 || i >= 8) Require(after[i] == (*pair.second)[i], "startup commit changed neighbouring bytes");
  }
  Require(LoadRawWord(MW3_STARTUP_GLOBAL_ADDRESS) == MW3_STARTUP_GLOBAL_VALUE,
          "startup commit changed owned data");
  VerifyHeader();
  startup_committed = true;
  std::fprintf(stderr, "MW3_STARTUP_COMMIT_CHECK_PASS:bytes=%08x pages=%u zero=1 neighbours=1 tail_reserved=1 nonce=%s\n",
               size, size / 4096, nonce);
  if (mode == "startup-bad-oracle") {
    std::fprintf(stderr, "MW3_STARTUP_MUTATION:%s nonce=%s\n", mode.c_str(), nonce);
    Require(result_size == size + 65536, "intentional startup commit oracle mismatch");
  }
  return;
#else
  diagnostic = "NtAllocateVirtualMemory";
  diagnostic_code = 86;
  std::fprintf(stderr, "MW3_STARTUP_STOP:before_commit=1 nonce=%s\n", nonce);
  throw rex::ThreadStop{86};
#endif
}

#ifdef MW3_STARTUP_EXECUTE
[[noreturn]] void StartupNext(PPCContext& ctx) {
  const char* nonce = std::getenv("MW3_ALLOCATION_NONCE");
  Require(startup_committed && allocation_inputs == 2 && ctx.lr == MW3_STARTUP_NEXT_LR &&
          ctx.r31.u32 == startup_frame, "startup next boundary/order mismatch");
  Require(ctx.r22.u32 == MW3_STARTUP_GLOBAL_BASE && LoadRawWord(MW3_STARTUP_GLOBAL_ADDRESS) == 0 &&
          LoadRawWord(startup_frame + 80) == startup_reserved, "startup heap base/global mismatch");
  auto bytes = current->GetGuestMemory().GetReadOnlySpan(startup_reserved, 1560);
  Require(bool(bytes), "startup heap header unreadable");
  auto half = [&](u32 offset) { return (std::to_integer<u32>((*bytes)[offset]) << 8) |
                                       std::to_integer<u32>((*bytes)[offset + 1]); };
  Require(LoadRawWord(startup_reserved + 16) == 0xeeffeeff && (*bytes)[5] == std::byte{1} &&
          LoadRawWord(startup_reserved + 20) == MW3_STARTUP_FLAGS &&
          LoadRawWord(startup_reserved + 24) == (MW3_STARTUP_FLAGS & 0x6001007d) &&
          LoadRawWord(startup_reserved + 60) == 0 && half(368) == MW3_STARTUP_FIELD &&
          half(58) == 1560 && half(0) == ((MW3_STARTUP_EXTRA + 128 + 15) & ~15u) / 16 &&
          ctx.r29.u32 == startup_reserved + 1560, "startup title heap markers mismatch");
  Require(LoadRawWord(startup_reserved + 76) == startup_reserved + 1432, "startup heap list head mismatch");
  for (u32 i = 0; i < 8; ++i)
    Require(LoadRawWord(startup_reserved + 1432 + 16 * i) == (i == 7 ? 0 : startup_reserved + 1448 + 16 * i),
            "startup heap list links mismatch");
  VerifyHeader();
  startup_heap_checked = true;
  std::fprintf(stderr, "MW3_STARTUP_HEAP_CHECK_PASS:markers=1 links=8 global=1 nonce=%s\n", nonce);
  if (mode == "startup-bad-heap") {
    std::fprintf(stderr, "MW3_STARTUP_MUTATION:%s nonce=%s\n", mode.c_str(), nonce);
    Require(LoadRawWord(startup_reserved + 16) == 0, "intentional startup heap oracle mismatch");
  }
  if (mode == "startup-incomplete" || mode == "startup-late") {
    std::fprintf(stderr, "MW3_STARTUP_MUTATION:%s nonce=%s\n", mode.c_str(), nonce);
    std::fflush(stderr);
    if (mode == "startup-late") std::this_thread::sleep_for(std::chrono::seconds(40));
    else omit_completion = true;
  }
  diagnostic = "KeGetCurrentProcessType";
  diagnostic_code = 86;
  std::fprintf(stderr, "MW3_STARTUP_STOP:service=KeGetCurrentProcessType lr=%08x before_call=1 nonce=%s\n",
               u32(ctx.lr), nonce);
  throw rex::ThreadStop{86};
}
#endif
