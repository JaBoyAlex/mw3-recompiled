# Reproducible host preparation

Canonical developer environment: Ubuntu 24.04 x86-64 with Clang 18.1.3, including Ubuntu under WSL on Windows. The eventual game runtime still targets native Windows. Tool preparation is independent of game files and requires no Steam/NVIDIA SDK or GPU. `lock.json` pins both CPU/shader source commits, all gitlink dependencies, compiler versions and official Microsoft DXC archive hashes.

Install Git, Python 3.11+, CMake 3.25+, Ninja and Clang 18 from your normal trusted package sources. On Ubuntu, `clang-18` supplies the host compiler. Then run from this checkout:

```sh
python3 tools/prepare_toolchain.py --fetch-sources --sources "$HOME/.cache/mw3-recompiled/sources" --output "$HOME/.cache/mw3-recompiled/toolchain-a"
python3 tools/prepare_toolchain.py --sources "$HOME/.cache/mw3-recompiled/sources" --output "$HOME/.cache/mw3-recompiled/toolchain-b" --compare "$HOME/.cache/mw3-recompiled/toolchain-a/manifest.json"
```

Keep source checkouts and builds in the native Linux filesystem when using WSL. Reusing a Windows Git checkout from Linux can fail the dirty-source check because of differing line-ending policies. The script refuses such a checkout instead of weakening verification. Use a persistent per-user cache: WSL `/tmp` may not survive a distribution restart.

The script fetches only missing pinned source trees when explicitly requested, refuses dirty/mismatched sources or submodules, verifies the downloaded DXC archive and extracted files, and never executes game code. It makes no package installs or security setting changes. All logs, generated fixtures, compiler binaries and reports remain in the output directory. Do not commit or distribute that directory. DXC's included license/notices remain with its package; no SDK/tool binaries are vendored here.

## What passes mean

The four original assembly fixtures have encodings independently assembled with LLVM 18.1.3. They are wrapped in a minimal ELF32 test container because the upstream loader groups sections by address; ordinary relocatable objects have overlapping zero section addresses. Our C++ harness checks 547 arithmetic, rotation, signed-branch and big-endian load/store results, returns nonzero on failure, and must also reject an intentionally mutated oracle. It does not rely on upstream's generated test main, whose assertions only print failures. The analyzer must process a synthetic ELF successfully.

An original HLSL shader is compiled by the hash-verified Microsoft DXC release to both DXIL and SPIR-V. Container magic and result hashes are checked. XenosRecomp is built against that library, but **Xenos instruction translation correctness and GPU execution are not established by this HLSL test**. There is no VMX128, floating-point/full-ABI, complete indirect-call or real-title coverage yet. These belong to later focused runtime and shader tests.

`manifest.json` records compiler, sources via lock hash, preparation/fixture hashes, tool binary hashes and generated result hashes. Own text-input hashes normalize CRLF to LF. Independent runs compare inputs and generated outputs. Host binaries can embed build paths/timestamps; no bit-for-bit binary reproducibility is claimed. The `host-toolchain` GitHub workflow performs both builds without private content or secrets.

## Native Windows status

The build driver can select Visual Studio 2022 ClangCL 19.1.5 using `--cmake <installed cmake.exe>` from Python on Windows. CPU and Xenos tool targets have linked locally. Defender has blocked a newly built analyzer copy; this path has not completed the full native synthetic suite. The owner restored the earlier analyzer, and that exact restored file passed a synthetic ELF test. No exclusion, rename-based evasion, protection change or automatic restore is performed by the project. Native host preparation remains experimental; use the verified WSL path for routine work.

Use `--skip-build` only to rerun validation of existing build outputs. `--compare <manifest>` still checks inputs, compiler and generated results. A successful compile or a tool printing usage is never reported as a translated-program test.
