# Stop boundary validation

The decommit-v1 baseline recorded exit 0 after the test requested exit 77.
The barrier-controlled fixture keeps the child outside the import until the
stop request completes. With the repaired profile, both NtYieldExecution
and the XAM XGetLanguage import record exit 77 with no return to the caller.
The thunk return path also preserves exit 77 when its native function requests
a stop. Explicit exits remain authoritative, including zero, 42, -17, and the
minimum signed 32-bit value. Earlier failing receipts remain in
[the thread evidence](../../../docs/engine/threads.md).

Five final thread profiles each pass 19 isolated cases, three combined orders,
and two negative checks. Across the five profiles this covers 380 ordinary
case evaluations and ten deliberate failures detected as expected. The profiles
cover Windows native and callback UBSan, plus Linux native, callback
ASan/UBSan, and SDK core ASan/UBSan. The core profile instruments base, PPC
and kernel. XAM uses the verified patched native library because its link
requires symbols supplied by the sanitizer test executable. Catch2 and the
graphics dependencies also use native builds.

Three CPU regressions each pass the 2,410-case synthetic oracle, reject one
deliberate wrong result, and reproduce the same generated C++ and header across
all three profiles. Three memory profiles each pass 60 synthetic processes,
including guarded page access and deliberately corrupted expected results.
The memory fixtures include exercises parameterized by the previously
verified image geometry, with original synthetic callbacks.

On both hosts, a copy of the verified package was accepted before mutation.
The verifier rejected separate byte changes to the thunk header and XAM
library. The rejections preserved the mutated bytes and both original
packages passed re-verification. A core receipt with a changed reference hash
for native XAM was rejected, and its original receipt still verified.

Public Release checks covered 108 Python tests on Windows with five explicit
tool/permission skips, and 110 on Linux with no skips. CTest passed on both
hosts, including ASan/UBSan on Linux.

## Reproduction

Run the preparation and thread commands from [the profile README](README.md).
For core instrumentation on Linux use an instrumented memory parent and add
`--core-sanitizers --native-report NATIVE_STOP_RECEIPT` to preparation. Use `--sanitizers` on the applicable test
commands. Run the memory and CPU drivers with the same explicit profile.

    python tools/test_runtime_memory.py --sdk-profile stop --root PRIVATE_CACHE --sdk-report STOP_RECEIPT --output-root PRIVATE_OUTPUT --metadata VERIFIED_GEOMETRY
    python tools/test_rexglue_ppc.py --sdk-profile stop --root PRIVATE_CACHE --sdk-report NATIVE_STOP_RECEIPT --output-root PRIVATE_OUTPUT
    python tools/check.py --config Release

On Windows the CPU oracle also takes `--reference` pointing to the successful
Linux fixture bundle. The CPU sanitizer profiles compile against a native SDK
and instrument the callbacks and generated test code. SDK and original source
identities, commands, case results, and log hashes are retained in each receipt.

## Source audit

- The import thunk and detour test the existing stop flag before and after
  native work. They now throw the derived cooperative stop tag. The kernel
  thread entry resolves it against the thread's stored requested exit.
- The wait path already calls CheckStop, which carries the stored exit code.
  The dispatcher rethrows the original exception, preserving its dynamic type.
- The spin path uses the new tag when a stoppable acquisition sees a pending
  stop. A fiber that sees the tag switches back without overwriting the
  previously recorded exit. The main fiber checks the stop on return.
- XAM instantiates GuestToHostThunk in its own binary. The pinned XBDM
  bodies do not instantiate the modified stop checks.

Direct execution evidence covers the kernel and XAM imports and the native
thunk's return path. Hook, spin, fiber, Windows full-core ASan and TSan are
outside the executed matrix. Real game execution and performance are untested.

| Profile | Private artifact directory | Manifest SHA-256 |
| --- | --- | --- |
| linux-sdk | `ac29774ed16c4aa1bcc1355d43b099bc` | `1be29426a9ca3acd8f42bfea92bac4075fd0230a06b9b0941cd879c393e5d25e` |
| linux-threads-native | `3f3b5da4873041dd94fca82c637ca343` | `59e967cbd583c15f9a725b6c1acfd8c6511c2d294a90910450d5f4f56c515b24` |
| windows-sdk | `fc7908c41cf54e3b8847c0afb8398c42` | `8b44b124e9c2fe0578e7256de42d3dd28f904316eb323a08bea328914931ff83` |
| windows-threads-native | `e8cef2f591ce4a6b8fd5e3e130844beb` | `6777b3f2483266bf18ee1bc49d973020e357f5f21b81580e968c98ba7b000e51` |
| windows-threads-ubsan | `d3a02982b93444c79b651615a2b17b2a` | `6fc8140c4afff01052310192c6793b1a87cecfc4485412d2afebcbed51f8a2ab` |
| linux-core-sdk | `d279d2140bce4add929904b439a4a883` | `8887f0c8a511f10414ef123b4ab2b0d54f3118f73b8f55a12e660a2780f08842` |
| linux-threads-core | `06c90bca54dd4057be7b8ebcd3541cd5` | `4be0b39c18d8b29b1f53536313e35c53bb2e0408cd2a5ffaa154c6e984570c10` |
| linux-threads-host | `a561f6a842714d159cd3fa3a8038e9d0` | `69d07dbb4327afe5dc220de80ab0852ae0f1cc8212636f5e525c6fd3bc06449d` |
| linux-cpu-native | `bf1da0971e864f4599f672be62327300` | `4fbb1bd7fdb22e417db8b217c8f88116578c50e9f6051bb96fde6fd590d034f2` |
| linux-cpu-host | `8419bd48df74406bb50a70b19306bfd6` | `7a40d3b17932100762cbe078ac66cc52b34dccf10d3a48cb50ea60d53f30853d` |
| windows-cpu-ubsan | `63b4ddc05e57441aa6b70565b4be1021` | `c9ad949170ce0851bfe40a2645be4d7d60d76ac477561e269f12b65d6bc41375` |
| linux-memory-native | `7849dcf6fca5419abfbd3e1561f89df8` | `4947f60275914690ec2fe0825bacaa3537c7aea0a04edfdfb35a95823768b5f7` |
| linux-memory-core | `2cf39015535c4180b764ccf13fcbf50f` | `ac1c3bdb7d0655b7e90d77073c03653ab1dabc349fabcda5c380a2fd9564360c` |
| windows-memory-native | `75fa9adb93d94cfdac4b35d8e34fc707` | `a47d025d0639df5eb181d636abf72075efba7b4b78c1a3da754066949efe3a98` |
