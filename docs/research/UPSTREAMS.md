# Upstream investigation

Checked 2026-11-17. Exact inspected revisions and license digests are in `config/upstreams.lock.json`. These are research pins, not a claim that any dependency is integrated. Source inspection is distinguished from upstream demonstrations; no upstream performance number is an MW3 benchmark.

## Required references

### [MW2 Recompiled](https://github.com/PaulCombal/mw2-recompiled)

The closest engine-family reference. Inspected `build.sh`, `CMakeLists.txt`, `runtime/title.h`, `runtime/online/steam.cpp`, `tools/xdvdfs.py`, and runtime/build/security docs. Its preparation generates separate SP/MP CPU modules; the host implements memory, kernel, devices and Vulkan graphics. `title.h` concentrates build-specific addresses, illustrating both the integration seam and how much title-specific verification remains. The pinned build applies a XenonRecomp patch; using unpatched upstream is not equivalent.

Candidate reuse: bounded disc import, device/runtime behavior, diagnostic traces, shader/prewarm cache design and engine-family security audit leads. `tools/disc.py` explicitly adapts its XDVDFS reader with bounds and budgets. No MW2 runtime or hooks have been copied. Validate every helper, structure and shader behavior for MW3.

Its [runtime documentation](https://github.com/PaulCombal/mw2-recompiled/blob/b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b/docs/runtime.md) describes coherent physical aliases, host guest threads and platform mapping requirements. Its [build documentation](https://github.com/PaulCombal/mw2-recompiled/blob/b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b/docs/building.md) is useful for ThinLTO/PGO and generated-input provenance. Those gains must be remeasured on MW3. Steam code defaults to AppID 480; that is not our production authorization strategy. GPL-3.0-only runtime reuse creates distribution questions for game-derived objects and vendor SDKs; do not assume an exception.

### [Co-op Anything](https://github.com/cranebeaker/coop-anything)

Inspected agent/contribution guidance, `tools/README.md` and automated QA/multi-agent playbooks. It supplies reusable concepts and game-independent tools for fault injection, traces, fake worlds, state oracles, scoped process pools, isolated saves and serialized game resources. Its own tool tests use fake clients: passing them does not prove a real game works.

Adopt the evidence discipline and scenario adapter pattern. Evaluate individual MIT-licensed chaos/flight/scenario pieces when an actual networking boundary exists. Do not introduce a replacement actor-ownership protocol for an already-networked game without need. Multi-instance couch play is distinct from preserving console-native split-screen. Our workflow also retains human visual/audio/input review rather than assuming every perceptual quality can be certified by bots. No upstream agent instructions are automatically adopted, and no code from these tools has been vendored.

### [NVIDIA Streamline](https://github.com/NVIDIA-RTX/Streamline)

Inspected the DLSS and Reflex programming guides, initialization/resource tagging and viewport lifecycle examples, `license.txt` and third-party notices. It offers integration plumbing, not missing engine data. DLSS/DLAA must receive trustworthy temporal inputs and separate viewport histories; Reflex needs frame-lifecycle markers. APIs include Vulkan and D3D paths, so an API rewrite solely to link a feature is not justified.

The source license grants permissive rights for covered framework code, with separately licensed components. Vendor feature DLLs and their SDK/redistribution conditions need individual review. Compile with no NVIDIA SDK by default. At the future integration gate, verify capability queries, signed binaries, initialization order, feature/resource teardown and graceful native fallback. No Streamline DLL/code has been incorporated. Do not equate source availability with unrestricted DLSS binary distribution.

### [Reverse Engineer Anything (REA)](https://github.com/morluto/rea)

Added at the owner's request. Use the official `morluto/rea` repository; similarly named forks and catalogs are not the authoritative implementation. REA is an agent-facing analysis MCP/CLI, not a CPU recompiler or graphics runtime. Inspect its provider support and evidence model before adopting it. Ghidra/IDA support alone does not establish XEX loading, big-endian PowerPC or VMX128 coverage through REA's own interfaces. MW3-035 must test the pinned provider with original synthetic PPC plus a private owned-title slice, preserve reproducible raw observations, and document unsupported instructions/file formats. No installer, provider or MCP configuration is run or changed automatically by adding this research reference.

## CPU, shader and runtime landscape

### [XenonRecomp / XenonAnalyse](https://github.com/hedge-dev/XenonRecomp)

Analyse is part of the same repository, not an independent runtime. Its function/switch analysis and PPC-to-C++ code generation are useful for AOT. Review README limitations: indirect calls, exception/nonlocal flow, MMIO and compiler-pattern-dependent jump tables. The related MW2 project adds relevant corrections. Begin conservatively, test instruction semantics/ABI, then assess local register allocation, SIMD endian shuffle efficiency and compiler optimization. Full-game correctness is not guaranteed by generated function counts.

MIT-covered tool code is attractive for reusable preparation tooling; inspect submodule/transitive licenses. A Windows tool build and an optimized generated runtime build are separate achievements. Record compiler, target ISA and helper patches. Portable baseline builds should not accidentally require the developer CPU's instruction set.

### [XenosRecomp](https://github.com/hedge-dev/XenosRecomp)

Generates HLSL for DXC compilation to DXIL/SPIR-V. The inspected README explicitly describes title-specific assumptions, incomplete dynamic indexing/control flow/reflection, vertex fetch and texture support. Use a representative shader/format corpus with synthetic edge cases before choosing it over the selected runtime's translator. Candidate benefits are shader specialization and reduced runtime compile work; format coverage and image correctness are gates. It supplies no memory manager, command processor or complete render backend.

### [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk)

Inspected runtime memory documentation, provider boundaries, PPC test pipeline, test CMake and the BSD-style license. Shared kernel/memory/devices and instruction tests may save substantial maintenance versus a title-specific fork. Its documentation explains physical views, MMIO recipients and host-page-size constraints; these are concrete test cases for our bakeoff. Its README also warns of API instability. Shared runtime scope may add overhead or different compatibility gaps. Measure a pinned version and upgrade deliberately rather than following latest automatically. Permissive licensing is a useful factor, not proof all transitive GPU/audio/tool components can be distributed unchanged.

### [Unleashed Recompiled](https://github.com/hedge-dev/UnleashedRecomp)

A shipped native port worth studying. Inspected module/submodule structure, memory code and renderer/cache layout; the README describes engine-aware native rendering, pipeline prewarming, bindless resources, transfer queues and input-aware pacing. Treat reported improvements as title-specific. Reusing techniques is more realistic than copying Sonic's render structures. Its plume submodule offers a rendering abstraction to evaluate only if we need both APIs. A new universal RHI is unnecessary for the first backend. GPL terms and separate third-party code apply.

### [CoD3Recomp](https://github.com/FrankHUN88453/CoD3Recomp)

The primary STATUS describes a different CoD-family port and concrete issues in swap packets, fence ordering, shader scalar operands, format swizzles and module address collisions. Useful regression leads: incorrect wait semantics can resemble poor performance; shader translation shortcuts can look right in one game and fail in another. These are upstream reported findings, not verified MW3 defects. Its renderer/engine/version are different; do not import addresses or assume feature parity.

### [Xenia](https://github.com/xenia-project/xenia) and other ports

Use Xenia as hardware-semantics/reference material and a possible differential oracle, not the native product or an infallible ground truth. ReXGlue and the shader ecosystem draw from this work; preserve file-level attribution when reused. Additional ports/frameworks enter the scorecard only with primary evidence, license/provenance and a comparable title slice. Popularity or a screenshot does not establish optimization, completion or maintainability.

## Next decisions

Select the runtime using MW3-008, shader translation on actual format/control-flow coverage, and graphics modernization after stable original output. Prefer contributing generic fixes upstream and keeping title-specific manifests/hooks local. Each adopted component needs pinned transitive inputs, a small regression suite and a named upgrade policy. Reassess architecture on new measurements; retire experiments that lose the comparison.
