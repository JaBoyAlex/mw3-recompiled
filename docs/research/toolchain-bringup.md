# CPU toolchain bringup observations

Date: 2026-11-17. Research pin: XenonRecomp `ddd128bcca99fe8bfbb99bea583c972351fa6ace` and its pinned gitlink submodules. These observations do not establish full toolchain reproducibility or MW3 CPU execution.

The installed Visual Studio 2022 MSVC compiler could configure the tool project but compilation failed on Clang `__builtin_bswap*` calls; the pinned project also selected C++17 despite newer library facilities. Reconfiguring with the installed **ClangCL 19.1.5**, x64, plus the repository's `cmake/toolchains/xenon-host-project.cmake` C++20 project-include override built both `XenonAnalyse` and `XenonRecomp` Release targets. The research source was not edited. This host-tool compiler choice is independent of the public metadata inspector, which builds under MSVC.

Windows Defender then quarantined the generated XenonAnalyse executable. Detection was confirmed in local Defender records at 2026-11-17 03:48 EST. We have not determined whether the detection is a false positive. No exclusion, restoration, rename/rebuild to evade detection, or protection change was attempted. The executable could not be launched; **no MW3 analysis tables were produced**. Private local logs preserve the failed launch attempts. The analysis task remains open pending an acceptable independently verified analysis environment or resolution through normal security review.

The recompiler executable remained present, but using it to bypass this detection is not the resolution. A complete toolchain task still needs shader/DXC builds, synthetic CPU/shader verification, manifests and repeatability checks. Do not mark MW3-006 complete based solely on a successful link. No title code was generated or executed.

For a permitted independent reproduction on Windows with Clang tools installed:

```powershell
cmake -S .local/upstreams/XenonRecomp -B .local/toolchain/xenon-clang -G "Visual Studio 17 2022" -A x64 -T ClangCL -DCMAKE_PROJECT_INCLUDE:FILEPATH="<workspace>/cmake/toolchains/xenon-host-project.cmake"
cmake --build .local/toolchain/xenon-clang --config Release --target XenonAnalyse XenonRecomp --parallel 2
```

Use the real absolute workspace path, initialize pinned submodules only from reviewed upstream URLs, and retain security protections. Research fetching does not initialize/build every submodule automatically. Do not retry quarantined executables without resolving the detection.
