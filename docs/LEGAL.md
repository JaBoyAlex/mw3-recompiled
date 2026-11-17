# Provenance, SDK and distribution decisions

This is a project policy and unresolved-issues register, not a conclusion that possession of game files grants rights to distribute derivatives. No copyrighted game content, translated/decompiled game code, keys or proprietary SDK files belong in Git/public CI. The owner supplies unchanged files. We do not acquire game content or console keys for contributors.

The project's original public tooling is GPL-3.0-only. `tools/disc.py` adapts the GPL-3.0-only MW2 XDVDFS reader with attribution. Standard GPL license text is in LICENSE. MIT/BSD-covered tools can be evaluated with notices preserved; actual runtime adoption requires file-level/transitive review.

Important unresolved combinations:

- MW2 and Unleashed GPL runtime code combined with game-derived compiled objects: omitting assets or requiring an owned disc does not itself satisfy GPL or grant game redistribution rights. Decide a permitted delivery model before distributing such binaries.
- Steamworks SDK, application authorization, wrapper/header/DLL terms and GPL compatibility: do not assume an upstream grant or the original game's AppID applies to us. AppID 480 is not a production plan.
- Streamline framework source versus NVIDIA feature DLLs, Nsight components and DLSS terms: review separately. Public framework source does not relicense proprietary dependencies.
- Dynamic linking, plugins or IPC are not automatic legal cures. No new exception can override copyrights in copied upstream code. Prefer a runtime and delivery model with clear compatible terms; obtain relevant permissions where needed.

Initially distribute only reviewed project source and game-free tools. Local generation is an engineering path to evaluate, not a blanket legal determination. Release contents require an allowlisted manifest, source/license notices, SBOM, hashes, SDK disposition and explicit treatment of generated objects. No game-linked binary release is authorized by passing CI. MW3-003, MW3-019 and MW3-031 track this work and unavoidable external permissions.
