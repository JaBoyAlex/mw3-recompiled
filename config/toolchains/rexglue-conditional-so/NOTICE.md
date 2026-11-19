# Conditional-store SO patch provenance

`atomic-so.patch` is original mw3-recompiled contributor work, licensed under
BSD-3-Clause to match its selected SDK target. Copyright (c) 2026,
mw3-recompiled contributors. All rights reserved. The conditions and disclaimer
are preserved in [the upstream license](../../../experiments/runtime-bakeoff/patches/LICENSE.rexglue).

The target is ReXGlue `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`,
`src/codegen/builder/memory.cpp`, whose Tom Clay copyright/BSD notice is
retained in the private overlay. The sole added emitter statement copies XER SO
to CR0 after either conditional-store outcome. It contains no game code or
guest address, changes no SDK ABI and does not repair reservation lifetimes.

The original preparation tool/CMake integration and reused project generator
adapter are GPL-3.0-only. A fresh private generator compiles the one-file overlay
alongside otherwise unchanged verified sources, linking the approved SDK
read-only. No existing SDK/source/package is patched in place. Nothing here
grants permission to redistribute SDKs or game-linked/generated binaries.
