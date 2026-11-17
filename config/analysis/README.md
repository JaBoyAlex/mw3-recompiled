# Owned-title metadata analysis

This is an initial inventory tool, not a game runtime or complete control-flow analyzer. Use only the exact owned executable pair from the versioned identity manifest and the [verified host toolchain](../toolchains/README.md).

On Ubuntu/WSL, after successful toolchain preparation:

```sh
python3 config/analysis/analyze.py --owned '<private SP/MP directory>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-a" --output "$HOME/.cache/mw3-recompiled/title-analysis-a"
```

The directory containing the two root executables can remain on the Windows drive under WSL; files are read-only. The script checks their exact hashes, the tool source/submodule revisions, preparation lock and analyzer binary hash. It then compiles a small metadata adapter against the prepared XenonUtils static library, records that library/probe identity, and captures image/import/switch observations. No guest code executes, decrypted image is dumped, key is logged, game data is uploaded, or original input is changed.

Use a new output directory each time. Logs, generated build files and full address inventories remain private; only sanitized observations and hashes belong in docs. The pinned upstream loader is not a hardened generic untrusted-file parser. Directly invoking `mw3-image-probe` bypasses the Python fingerprint guard and is unsupported for unknown files.

All detected entry/dispatch/target addresses must fall within executable sections. Invalid registers, empty targets or duplicate dispatches fail validation. These checks do not find omitted switch tables or prove import/function/ABI completeness. See [current findings and remaining work](../../docs/engine/executables.md).
