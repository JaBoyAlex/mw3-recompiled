# Native Windows compatibility patch

Original changes in `rexglue-win32-procedure-types.patch` are licensed under
BSD-3-Clause to match the modified SDK file. Copyright (c) 2026,
mw3-recompiled contributors. `memory_win.cpp` retains its upstream Ben Vanik
2020 notice and Tom Clay's 2026 adaptation notice. The thread source retains
Tom Clay's 2026 notice, and the D3D12 provider retains its upstream notices.
The upstream conditions and
disclaimer are in [LICENSE.rexglue](../../../../experiments/runtime-bakeoff/patches/LICENSE.rexglue).

The patch explicitly transfers the address representation returned by
GetProcAddress into the declared Windows API function-pointer types in memory,
thread naming and D3D12 loading. It also corrects SetThreadDescription's return
type from HANDLE to the Windows SDK's HRESULT and specifies WINAPI. Other
function signatures, symbol names and missing-API failure checks are preserved,
with warnings-as-errors enabled. It does not alter allocation policy or
relax a runtime guard. The private preparation manifest binds the composition
of this patch and the separately reviewed base memory/output-directory patch.

Project Python tools retain GPL-3.0-only. No GPL code was copied into this patch
and no SDK/game-linked redistribution permission is granted.
