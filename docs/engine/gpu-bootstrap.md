# Native D3D12 bootstrap and readback — MW3-050

The actual unchanged selected SDK D3D12 driver creates a hardware device and
owned hidden surface, submits original RGBA8 clears/copies and returns expected
pixels on this machine. This is a synthetic **host graphics foundation**. It
does not run Xenos guest commands, translate MW3 shaders, attach a title or
establish a rendered MW3 frame, menu, fidelity, split-screen or playability.

## Boundary, construction and provenance

`tools/test_gpu_bootstrap.py` verifies the approved native memory-profile
SDK/source receipt before creating output. It builds a fresh private copy of
the original diagnostic with pinned Clang 20.1.2, O2, x86-64-v2, native MSVC
headers and two workers. SDK-facing headers require C++23; the maintained public
core remains C++20/Python standard library. All SDK/source/package files stay
read-only; no SDK repair or runtime/startup/input interface changes occur.

The probe explicitly loads verified `rexgpu.dll` and
`rexgpu-xenos-d3d12.dll`, obtains versioned real interfaces and selects the sole
`d3d12` Xenos-family registration. The real graphics-system interface supplies
settings to the provider; the probe drives that actual provider's lifecycle
directly. It does not start the full application/present thread or fabricate
guest services. A small owned UI dispatcher executes/queues actual callbacks.
Driver initialization, surface attachment and one blank host present precede
the separate render-target readbacks. No result is called an MW3 frame.

The pinned source's inline `GetProvider`/`GetDevice`/`GetDirectQueue` accessors
identify the **same SDK device and queue** used by this work. This private-header
introspection is diagnostic-only and bound to exact source/package/compiler
identities; it is not a stable production ABI. `REX_GPU_XENOS_STATIC` matches the
provider's statically embedded base and compiles its inline accessor locally.
An initial DLL-import link failure is retained; no SDK export was added.
Original project source is GPL-3.0-only. Referenced private ReXGlue/Xenia
headers retain their existing BSD provenance; Windows/DXC headers and SDK
binaries are not copied into Git. No new game-linked distribution right follows.

Each process owns its hidden Win32 window, resource heaps, command lists,
events, fence, module references, UI queue and private temporary/profile/output
directories. Explicit library paths and post-run hashes bind actually loaded
SDK modules. Software adapters are rejected from hardware evidence; there is no
null/WARP fallback or automatic backend substitution. Global OS/display-driver
cache state is not reset or claimed private. No GPU-heavy real-title suite ran
concurrently, and local heavy builds were serialized.

## Verification and negative controls

Eight original inputs include 1-, 3-, 17-, 19-, 31-, 63-, 64- and 65-pixel
widths, nontrivial alpha/color bytes and non-square dimensions. Four colors are
fixed and four deterministic seeded values. Every visible RGBA byte is checked;
the independent Python expected pixel-stream hash checks the returned data
again. Readback row pitch/padding is respected and checked without treating
padding bytes as image pixels. There is no shader/game input.

The texture transitions from render target to copy source; an actual GPU queue
signal and bounded fence event complete before mapping the readback buffer.
Map alone is not synchronization, as documented by Microsoft's
[readback guidance](https://learn.microsoft.com/en-us/windows/win32/direct3d12/readback-data-using-heaps).
The footprint and copy follow the documented
[GetCopyableFootprints](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device-getcopyablefootprints)
and [CopyTextureRegion](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12graphicscommandlist-copytextureregion)
contracts. Original code implements these calls; no sample implementation is copied.

The completion protocol requires exact nonce/case/schema/types, eight rows per
cycle, expected per-row hashes/dimensions, actual non-software adapter identity,
fence completion, empty UI queue, two released module references and zero SDK
error-level messages, including teardown. An owned logger sink observes errors
without replacing the SDK logger. GPU debug messages are checked when that
layer exists. Duplicates, stale/partial output, changed module paths, coercions,
missing/changed pixels, resource counts, timing bounds and nonzero exits fail.
Compiler/tool/source/producer/probe/package identities are rechecked afterward.

Wrong-pixel control executes an actual GPU clear/copy/fence/map, then changes
one CPU-side observation and requires its exact mismatch failure. Incomplete
control executes and cleans up but omits completion. Deadline control emits a
plausible complete record after actual cleanup, then stays alive; the parent
kills/waits only for that owned child after eight seconds and requires rejection.
It does not deliberately hang the GPU. The five-second GPU-fence-timeout branch
is implemented diagnostically but was not forced; GPU fault recovery is unverified.

Eleven public Python tests exercise those evidence boundaries with explicitly
synthetic records and a real bounded Python child. These fixtures load no SDK
or GPU. Bytecode caches are excluded from maintained-source identity, while
source mutations remain bound. An earlier post-run comparison correctly rejected
bytecode-cache differences; its otherwise passing executions remain separate
development evidence, not an accepted final receipt.

Both actual native probe binaries also pass eight CLI/input rejection cases
each: missing arguments, unknown case/control, bad nonce, seven/nine input rows,
oversized width and out-of-range color. All 16 return the expected failure code
and exact diagnostic before loading graphics interfaces or creating a GPU
device. These are actual C++ input checks, distinct from the Python fixtures
and from ordinary GPU evidence.

## Actual local matrix — 2026-11-19

One Intel Core i5-11400 / NVIDIA GeForce RTX 3060 Ti machine runs native Windows
11 x64 build 10.0.26300, Clang 20.1.2. The actual SDK device's adapter is vendor `0x10de`, device
`0x2486`, non-software, with DXGI-reported dedicated bytes **8,413,773,824**.
The adapter's own interface-support version is **32.0.16.2124**, matching the
separate OS inventory. WMI's truncated 32-bit AdapterRAM is not used for VRAM.
This is one hardware/OS tier, not NVIDIA/AMD/Intel coverage or a minimum spec.

Each profile has three independent bootstrap processes, three independent
three-cycle lifetime processes, a held-out-color process and three controls.
Seven ordinary processes pass 13 device/surface lifecycles, 104 completed
readbacks and **57,057 verified original pixels**. Both native and supported
host UBSan profiles pass: 14 ordinary PASS processes, 26 lifecycles, 208 readbacks
and 114,114 verified pixels, plus six expected-control PASS processes. Counts
exclude partial/control results from ordinary compatibility totals. Actual
SDK error/warning counts are zero in the accepted ordinary records.

The native SDK, OS graphics runtime and display driver remain uninstrumented.
Windows host UBSan uses undefined traps with vptr disabled; positive calibration
exits zero and deliberate signed overflow traps with exit `3221225501`.
That proves the selected host instrumentation is active, not SDK/GPU memory safety.

**SKIP:** D3D12 debug layer, `D3D12GetDebugInterface` returns `0x887a002d`
(SDK component missing). Zero debug-message counts therefore do not establish
validation-layer cleanliness. **NOT RUN:** native Vulkan, WSL GPU execution,
AMD/Intel adapters, Windows core ASan/TSan, full SDK live-object/leak accounting,
device-loss/TDR recovery, Xenos shaders/packets, formats beyond this RGBA8 clear,
depth/resolve/color-space parity, title startup or console captures.

### Sealed identities

ReXGlue source pin is `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d` plus the
unchanged approved native memory derivative.
The verified derivative Git tree is `0b8453b70039c1ef22a70b4d41f507fc91f5e530`,
with composition patch SHA-256
`f04188b8bfef1dfd8f7654b20c546f9c64793a7c6e28ffc5896215754184e433`.
Receipts retain every command,
seed/order, source/helper/tool, executable, input/log and artifact identity.
Final collection rehashes all retained artifacts and reclassifies every result;
private logs/binaries/manifests remain outside Git.

| Artifact | SHA-256 |
| --- | --- |
| Diagnostic producer | `6a69823809d7554c851e5edf7286327beacaea32a9d3710f73b8c34c4d97bf22` |
| Maintained __init__.py | `005968a953091e26becb75148418187a7737a57731485eec99d23fc07a6677b9` |
| Maintained CMakeLists.txt | `4460df8cc4fb2b6ca67ca79e13b6ad1bf8f2696b0a94b4c59b70000c1355cdf7` |
| Maintained probe.cpp | `d2b174c9e542364fa29901e2792cc8a3c580e1eb59f8b45c97220154a1d6154f` |
| Maintained test_evidence.py | `968f2c8a14dba4ab872d34b498b9d3f3466dd57b0ac7068604e49396be4c7acf` |
| Approved native SDK receipt | `4744ae8546dd7f79728dbbb5f53afb66bca983d2b2e58a28ac495780af8ac8f8` |
| Unchanged SDK package tree | `8e0ac9324376d04668025dd8c97caa680c45c3d329d80f49f0ab0b28f9787f4d` |
| Actual loaded provider | `c22c690b47e87dcf57ace86ec10f4ea47a8bfe1026ba349abb4bf938f280b66a` |
| Actual loaded graphics | `e1ea7e1a227e97caacd732c5e70fbc5865477fbb4b6872d24dad8a6184348447` |
| Actual loaded base | `b9fa2b6e94ed6bd2d952d0c8e03a743da0a769eba43a0ca3e6524511475f05ff` |
| Build tool cxx | `0eb656a5c9f59d040a3a1cfd09a0dfabc22241528ea917ad07daa1d9037e2d15` |
| Build tool cmake | `6fe2e6431b45cf32b9b2f3e50a8efae046a2366eb34d0fb36da027cf56102aec` |
| Build tool ninja | `ff29bcb5f547174bae6b73c84278cce9b674e8ebc2f3c3926ab21030b33f34b8` |
| Build tool git | `20d0dde30a65afb6e5810a883700a94dcd77fbf3b44b32868d45bf7c9b30137c` |
| native execution receipt | `9e404ecdc128b8d2b8f7bbf57dbc6a86ce90450e92102a658d03895efffb1c73` |
| native executed probe | `1de64d37c5aed702934ba83f09c2b238e3187ad07fbff35e2bfa450abedc1db7` |
| native compile commands | `fcfd150f4f922e0d4b1cd182fd928485ac19f30107717cacf83100e85f263d57` |
| host-ubsan execution receipt | `7c6175bb5d6baf98f1f28614fc87f036bde3a6b5d552976c12a06b19f05e46b3` |
| host-ubsan executed probe | `ba2122b1bb37522722413ea4b29cfa9f5d6193adb727c2c2bd100c37da089716` |
| host-ubsan compile commands | `c6fa2f993a54aa0e0932726cdde37524aa93de666780618ab4d547d4117ad454` |
| host-ubsan calibration executable | `403d3508353a7738a9e03d4b999e5d84befcb86ee2ab099d8f30f28dffa89a9b` |
| Sixteen actual CLI/input rejections receipt | `609da137e7b5816833bbf3ec52756f076900a6130c996ac440c602a581a050da` |

The native and UBSan receipts rehash 89 and 94 retained artifacts respectively.
Source/profile/package and actual loaded SDK byte identities agree throughout.

### Measured host costs

Each table row is one process. Initialization/cleanup lists contain one value
per device cycle, in milliseconds; completion p50/p95/max is in microseconds
over eight readbacks (bootstrap/heldout) or 24 (lifetime). No warmup/sample is
discarded. First device initialization is cold to that process; repeated cycles
and OS/driver caches may be warm. Runs were native first, then host UBSan,
with no controlled background-load isolation or randomized instrumentation order.

| Profile / case / repeat | Initialization ms | Cleanup ms | Completion p50 / p95 / max us |
| --- | --- | --- | --- |
| native / bootstrap / 0 | 349.128 | 28.568 | 88.75 / 120.30 / 120.30 |
| native / bootstrap / 1 | 348.356 | 30.076 | 86.25 / 104.60 / 104.60 |
| native / bootstrap / 2 | 348.933 | 36.924 | 79.35 / 131.10 / 131.10 |
| native / lifetime / 0 | 348.281,243.225,244.755 | 29.441,23.213,22.580 | 75.00 / 84.80 / 95.90 |
| native / lifetime / 1 | 349.866,241.649,245.559 | 32.708,22.283,22.271 | 75.70 / 97.10 / 100.60 |
| native / lifetime / 2 | 349.590,244.703,239.823 | 30.147,23.182,22.833 | 76.70 / 114.70 / 140.60 |
| native / heldout / 0 | 351.645 | 30.510 | 76.05 / 90.70 / 90.70 |
| host-ubsan / bootstrap / 0 | 347.913 | 34.353 | 73.25 / 110.40 / 110.40 |
| host-ubsan / bootstrap / 1 | 356.350 | 29.687 | 82.85 / 107.70 / 107.70 |
| host-ubsan / bootstrap / 2 | 373.754 | 31.594 | 76.80 / 85.50 / 85.50 |
| host-ubsan / lifetime / 0 | 349.633,245.061,245.184 | 30.606,22.994,21.875 | 75.90 / 82.30 / 120.30 |
| host-ubsan / lifetime / 1 | 354.642,242.609,245.115 | 28.535,22.519,21.792 | 73.50 / 83.50 / 102.60 |
| host-ubsan / lifetime / 2 | 349.030,252.652,242.034 | 29.538,22.512,23.270 | 77.70 / 94.40 / 103.40 |
| host-ubsan / heldout / 0 | 354.011 | 43.379 | 76.40 / 118.00 / 118.00 |

The completion interval includes CPU submission, GPU scheduling/work, fence
notification and host wakeup; it is not a GPU timestamp or frame time. Allocation
and pixel comparison are outside that interval. Initialization includes the
hidden host present. Native bootstrap initialization is about 348–349 ms and
cleanup 29–37 ms in these three samples. Timing granularity is 100 ns. The tiny
sample sizes and uncontrolled caches/load cannot prove speed, regressions,
frame pacing, input latency or comparative renderer performance.

Keep the already selected backend for bounded diagnostics, and retain this probe
as a pre-integration prerequisite check. Full correctness and distribution gates
remain unsatisfied. Performance 30%, stability 25%, maintainability 20%,
integration effort 15%, hardware compatibility 10% remain **unknown** as MW3
architecture scores; no weighted total or fastest-framework claim is made.
The private-header dependency needs explicit review/replay on SDK upgrades.

## Reproduction and handoff

```text
python tools/test_gpu_bootstrap.py --root <private-native-root> --sdk-report <approved-native-memory-manifest.json> --output-root <fresh-private-output>
python tools/test_gpu_bootstrap.py --root <private-native-root> --sdk-report <approved-native-memory-manifest.json> --output-root <fresh-private-output> --sanitizers
python -m unittest discover -s tests/gpu_bootstrap -p test_*.py -v
python tools/check.py --config Release
# WSL/public suite; this does not execute a GPU:
python3 tools/check.py --config Release --sanitizers
```

Public Windows checks pass 265 Python tests/eight explicit skips and native
parser CTest 1/1. WSL checks pass 265 tests/two Windows-only skips and parser
ASan/UBSan CTest 1/1. All eleven GPU protocol tests run on both hosts. Task DAG
(61 tasks), artifact heuristic and staged whitespace review pass, plus manual
provenance/source-scope review. Public CI is game-free and does not certify
these separately identified private GPU executions. Self-review only; no
independent reviewer is represented.

Next integration prerequisites remain: the lead's allocation/startup ABI work,
an agreed bounded title GPU service/command submission contract, actual MW3
shader/resource/resolve discovery and console captures. Enable/install the
optional graphics debug component before claiming validation-layer coverage;
it was not installed or hidden here. Other GPU vendors/backends need separate
owned hardware observations. This task leaves the first-frame epic incomplete
and does not reserve or alter runtime/gpu, the guarded startup harness, input,
SDK/source packages or game content. No paid Actions or billing changes are made.
