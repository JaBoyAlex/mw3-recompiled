# Native Windows bring-up — in progress

Task 040 is not complete. The selected SDK is being built natively with
Clang 20.1.2, MSVC tools 14.44.35207 and Windows SDK 10.0.26100.0. No Windows
title checkpoint or gameplay result is claimed by this preparation checkpoint.
The [Linux header checkpoint](startup-imports.md) remains separately verified.

The [profile lock](../../config/toolchains/rexglue-windows/lock.json) records the
official [LLVM 20.1.2 release](https://github.com/llvm/llvm-project/releases/tag/llvmorg-20.1.2)
archive, locally recorded SHA-256/size, source revisions and Windows API typing
patch. Compiler extraction keeps required tools, runtime/resource headers and
libraries in a private cache; it does not install globally or change PATH
permanently. The complete original compiler archive is retained. Its digest
is recorded from the official TLS download; no signature verification is claimed.

```powershell
python tools/prepare_windows_runtime.py --root <private-cache> --fetch --build
```

An existing matching compiler can first be checked with `--compiler-only`.
Subsequent builds omit `--fetch`. Each attempt retains a separate manifest and
logs. Source edits outside the exact reviewed patch composition fail rather
than being reset. Native/sanitizer outputs must remain isolated. Two build
workers are the limit. This is development tooling, not an installer or release.

Vulkan headers/VMA and a genuine import library made from the pinned official
[loader definition](https://github.com/KhronosGroup/Vulkan-Loader/blob/fb78607414e154c7a5c01b23177ba719c8a44909/loader/vulkan-1.def)
satisfy the build dependency without installing a separate graphics SDK. The
runtime loads graphics implementations dynamically; neither renderer nor any
device/driver capability is validated by compilation. No game content is used
by SDK preparation. Vendor SDK or game-linked distribution remains unapproved.

Observed preparation issues are retained:

- The archive's version output puts a newline after `20.1.2`; version checking
  now accepts a word boundary, while still checking exact package/file hashes.
- MSVC's batch environment needs correct cmd quoting and case-insensitive
  environment-name handling. The helper captures it privately and records only
  selected tool/SDK fields, never a complete environment dump.
- glslang's legacy FindPythonInterp found the Windows Store alias instead of a
  usable interpreter. CMake now receives the exact running Python executable.
- Clang diagnosed incompatible generic GetProcAddress casts in SDK Windows
  memory/thread/D3D12 loading. The narrow BSD patch uses explicit address
  representation transfer into the declared function types. Review also found
  and corrected SetThreadDescription's return type to the installed SDK's
  HRESULT/WINAPI declaration. Missing-API checks and warnings-as-errors remain.

The guarded host now uses the SDK's DynamicLibrary abstraction rather than
Linux-specific dlopen/dlsym. Both Linux titles retain their header-query/next
trap behavior across the 24-case native/host-sanitizer regression matrix.
Private report: `kernel-bringup/recheck-1d15916388434e4aa9d1163420b1e25a/manifest.json`,
SHA-256 `f525b7dde2c17a498ed2b84c60550eb641ec78ac25b5566c532993ab77f085bf`.

The lead extends 040's reservation to the two existing guarded host files for
this platform abstraction change and its CMake dependency. No other developer
owns those files; memory/CPU/thread test lanes retain their disjoint scopes.
Windows import bindings must be verified before any title thread launches;
platform differences cannot be handled by removing the guard or admitting
unreviewed SDK exports.

Remaining acceptance: complete/verify native SDK artifacts, native host tests,
compile the verified SP/MP modules, reproduce three guarded title checkpoints
per executable and meaningful negative cases, compare with Linux, and publish
actual hashes/limitations. All product gates remain open. No performance result,
independent review, complete kernel compatibility or release approval is implied.
