# Native Windows bounded startup — 2026-11-17

Both owned SP/MP executables execute translated startup natively on Windows,
pass the reviewed header service and stop at guarded **NtAllocateVirtualMemory**.
Three independent positive processes and three rejection cases pass per title,
matching the [Linux checkpoint](startup-imports.md). This is not playable boot,
rendering, gameplay or orderly teardown. Twelve other data imports and later
function services remain unreviewed; kernel/product gates remain open.

## Reproduce private preparation

The [lock](../../config/toolchains/rexglue-windows/lock.json) pins official LLVM
20.1.2, MSVC tools 14.44.35207, Windows SDK 10.0.26100.0, recursive SDK sources and
an API typing patch. The [LLVM archive](https://github.com/llvm/llvm-project/releases/tag/llvmorg-20.1.2)
is locally fingerprinted, not signature-verified. Selected tools and resource
headers/runtimes are extracted privately; the complete original archive remains.
No permanent PATH, security or global installation changes.

```powershell
python tools/prepare_windows_runtime.py --root <private-cache> --fetch --build
```

Later builds omit `--fetch`. `--compiler-only` checks an existing compiler.
Each attempt retains a manifest/logs. Unknown source edits fail without reset.
Two build workers are the limit. Configuration requests O2, but upstream SDK
target options append O3; do not claim an all-O2 profile or equivalent Linux
optimization settings. No gameplay performance or speed ranking is measured.

Pinned Vulkan headers/VMA and a genuine dlltool import library from the official
[loader definition](https://github.com/KhronosGroup/Vulkan-Loader/blob/fb78607414e154c7a5c01b23177ba719c8a44909/loader/vulkan-1.def)
meet build dependencies without a separate graphics SDK. Compilation validates
no GPU/driver behavior. SDK/game-linked distribution remains unapproved.

## Reproduce guarded execution

Generate the private cache using [task 009](../../config/recomp/validation-2026-11-17.md)
on the verified Linux preparation profile, make it locally accessible to Windows,
and provide its independently recorded receipt fingerprint:

```powershell
python tools/prepare_windows_runtime.py --root <private-cache> `
  --reference-cache <reviewed-local-generation-cache> `
  --expected-generation-sha256 <verified-manifest-sha256> `
  --sdk-report <private-sdk-build-manifest.json> `
  --owned <private-original-xex-pair> --metadata <verified-analysis-directory> `
  --role sp
```

Repeat for `mp`. Add `--host-sanitizers` for host/parser UBSan trap checks and an
original inert safe/overflow calibration. No private files are uploaded. A local
receipt supplies provenance, not signed attestation or permission to run an
arbitrary supplied binary. The helper verifies exact title/recipe/tools, full
payload, compiler and SDK, stages an immutable copy and rejects mutations without
repair. CMake path arguments use forward slashes to avoid `\U` escapes.

The host uses SDK DynamicLibrary APIs, verifying every function binding before
launch. Only RtlImageXexHeaderField is admitted and compared with the bounded
independent reader. The used module-handle cell/header chain matches the owned
header. Four additional present-field audit queries are **host-initiated** using
a copied PPC context, not original guest-flow calls. Binding/pointer/result
mutations reject actual lookup/call outcomes. No success stubs or maintained
translated source are introduced.

Each process has private profile/temp/config roots, headless devices and timeout.
Expected exit 86 identifies the unknown-service stop; exit 87 identifies guard
refusal. Both use `_Exit`, so normal destruction, title teardown and leak checking
remain unverified. Independent instruction inventory confirms matching returns:

| Executable | Header return | Next NtAllocateVirtualMemory return |
| --- | --- | --- |
| SP | `82462e8c` | `824652e4` |
| MP | `824e4b2c` | `824e6f64` |

## Verification and limitations

- SDK build/install passes with 751 fingerprinted installed files.
- 255 selected game-free SDK tests pass in separate Windows processes. Linux's
  selected set has 261; counts do not establish identical sets or aggregate-suite
  success. Aggregate/lifecycle defects remain with 039. LNK4217 warnings remain
  visible in build logs.
- Native title matrix: 12/12 processes pass. Host-only UBSan trap matrix: 12/12
  pass; safe input returns 42/exit 0 and signed overflow exits `0xc000001d` in an
  independent calibration. SDK/generated objects remain uninstrumented.
- Linux loader regression: 24/24 native/host-ASan/UBSan processes pass. Public
  parser checks also run on Windows/Linux and Linux ASan/UBSan. Public CI never
  executes game code or proprietary SDKs.

Independent Windows ASan calibration works, but the title link fails because the
SDK allocator shim and ASan define the same allocation operators. An earlier
mixed build also exposed STL annotation disagreement. Do not force duplicate
symbols or replace one side of the allocator ABI. Standalone UBSan reporting
fails its static-CRT versus SDK dynamic-CRT link requirement. The Windows profile
uses documented [UBSan trap mode](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)
without a runtime; it provides no source-level runtime diagnostic. Compatible
Windows ASan/cross-DLL allocator instrumentation needs separately scoped work.

Retained preparation failures cover version-output newline, MSVC batch quoting/
environment-name case, glslang selecting Store Python and incompatible
GetProcAddress casts. The BSD typing patch transfers addresses into declared
function types and corrects SetThreadDescription to HRESULT/WINAPI, verified
against the installed header. Warnings-as-errors and missing-API checks remain.
No antivirus bypass was used.

## Private evidence index

Relative to the owner's Windows cache unless marked Linux. Full commands,
outputs, negative-case logs and artifact/source hashes remain private.

| Evidence | Manifest | SHA-256 |
| --- | --- | --- |
| SDK | `runs/c52e67df3a5b4244beb5faa78dfb5871/manifest.json` | `5b857fdfd2311b3a215c64fc1114c16c3958337766aef4fa0ee5b12372a3f34c` |
| Isolated SDK tests | `host-tests/dd487e874b6947168b10a56298d7d07e/manifest.json` | `65338d705653b5dffe72773f312ce42b514f9ef228cabab5855008d046139612` |
| Native SP | `runs/c4b7fc2e48044c1daee6d85189c4f9e5/manifest.json` | `8da1107764aae8a1b944ae6d6a8994ae1b47b0b856798d1dddefd97309a1b143` |
| Native MP | `runs/d76a5de712a54819b8ec1a8bb14f4b4b/manifest.json` | `77dea75dcf28a6bc9c68a88983ae1107b4432af2709053744034682ef0b879ae` |
| Host trap checks | `sanitized-probes/16f499b578d243edb98d22e0aafeedca/manifest.json` | `f125dbeade9e8ffac7b23e2d72a638f2af32591378089ca831673f1aa8dd2f05` |
| Trap calibration | `sanitizer-calibration-final/manifest.json` | `4af6f1233a000d1be01914e06c2c5fe43b4f5761229db243a15ed07e7e87e9d9` |
| Linux loader regression | `kernel-bringup/recheck-1d15916388434e4aa9d1163420b1e25a/manifest.json` | `f525b7dde2c17a498ed2b84c60550eb641ec78ac25b5566c532993ab77f085bf` |

The lead extends 040's reservation to guarded host/CMake, README, architecture
and agent/status summaries. No other owner overlaps. Self-review is recorded;
no independent review is claimed. This completes bounded Windows preparation,
not kernel milestone 010 or first-frame 011.
