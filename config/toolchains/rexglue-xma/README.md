# Decoder packet ownership profile

MW3-044 is in progress. `xma-packet-v1` derives from the reviewed stop-v1
profile. It composes that exact parent's patches with one original packet
destructor call. It rebuilds/replaces only the affected kernel shared library;
public headers and every other packaged file retain their parent hashes.
Baseline source worktrees, SDK packages and failing observations are preserved.

```text
python tools/prepare_runtime_xma.py --root PRIVATE_CACHE --baseline-report STOP_RECEIPT --fetch
python tools/test_runtime_xma.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --sdk-profile xma --output-root PRIVATE_OUTPUT --sanitizers
python tools/verify_kernel_gate.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --sdk-profile xma --owned OWNED_PAIR --metadata VERIFIED_METADATA --generation GENERATION_RECEIPT --expected-generation-sha256 RECEIPT_SHA256 --output-root PRIVATE_OUTPUT --role sp --sanitizers
```

Omit `--fetch` after the isolated source/submodules exist. Core sanitizer
preparation takes the instrumented stop parent and `--core-sanitizers`.
The standalone diagnostic accepts that profile with `--sanitizers`; native
SDK plus host sanitizers remains a separate observation. Windows supports
native SDK and host UBSan traps; instrumented core/ASan remains unsupported.
Preparations are exclusive per cache and build with at most two workers.

The game-free fixture loads an empty image and tests destruction without
launch. Its launch-error cases attach the actual APU/context pool before
rejecting the missing executable module, then require unload and destruction.
Four consecutive pool lifetimes run in one process. No guest code executes.
The owned-title matrix separately tests successful real-module launch through
the bounded diagnostic checkpoint. These checks do not verify audio playback.
