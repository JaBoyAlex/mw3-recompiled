// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
#include <cstdint>
struct Image;
// Called once by a private, mechanically instrumented pinned loader source,
// immediately before its import-normalization loop. This observer writes nothing.
void mw3_observe_imports(const Image&, const uint8_t*, std::size_t);
