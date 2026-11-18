# mw3-recompiled

An early research and engineering project for a native PC version of **Call of Duty: Modern Warfare 3 (2011)** using the owner's Xbox 360 files. **Not playable.** Private native Windows/Linux programs execute bounded translated SP/MP startup through one audited header service to a guarded memory-service stop. Gameplay remains unverified. The repository provides executable inspection, owned-disc identification, build/test infrastructure and a dependency-aware contributor backlog.

The chosen architecture is ahead-of-time Xbox 360 CPU recompilation with ReXGlue and selective native replacements. [The runtime decision](docs/adr/0002-runtime-selection.md) records correctness failures, a focused Linux memory repair and limits of the comparison. Full decompilation is not a completion metric.

Targets: full Campaign, Special Ops, Survival and Multiplayer; original local/online split-screen capabilities; planned four-player Survival extension; authenticated Steam friend invites/private lobbies and SDR where authorized; optional DLSS/DLAA and Reflex where technically and legally practical. None of these gameplay/network/graphics targets is implemented here yet.

## Start contributing

Requirements: Git, Python 3.11+, CMake 3.25+, a C++20 compiler. Windows: Visual Studio 2022 Build Tools with Desktop C++ and a Windows SDK. Linux checks use GCC/Clang and Ninja. The initial inspector has no external libraries or SDK requirement.

```powershell
python tools/check.py
python tools/project.py list --ready
python tools/project.py prompt MW3-006
```

Use `--config Release` for optimized host-tool checks. If CMake is not on PATH, pass `--cmake <path>` and `--ctest <path>`. CMake presets also support Ninja (`dev`, `release`, `asan`) from a compiler-ready shell. See [build instructions](docs/BUILDING.md).

Claim a task using the GitHub Actions `task-admin` workflow, then use an isolated worktree. [CONTRIBUTING](CONTRIBUTING.md) explains small-team lanes, claims, prompts and PR evidence. [AGENTS.md](AGENTS.md) is the agent contract; project skills live in `.agents/skills/`.

## Inspect owned files

```powershell
python tools/inventory.py '<owned MW3 disc>.iso' --label xbox360-rev1 --output .local/iso-identity.json
python tools/disc.py '<owned MW3 disc>.iso' --output .local/disc-identity.json
```

Create `.local` first. Reports never imply ownership verification or supported gameplay. Disc inspection is read-only; optional `--extract-executables .local/game/rev1` copies only the two title executables without overwriting existing files. Keep outputs and game bytes private. Originals remain unchanged. The owner-supplied Rev 1 image has been inspected; exact non-content identity is in [title identity](docs/research/title-identity.md).

## Project navigation

- [Current status and verified checks](docs/STATUS.md)
- [Friends: easy Codex onboarding and copyable prompt](docs/FRIENDS-START-HERE.md)
- [Architecture and alternatives](docs/ARCHITECTURE.md)
- [Dependency-driven roadmap](docs/ROADMAP.md)
- [Upstream technical investigation](docs/research/UPSTREAMS.md)
- [Decision and benchmark scorecard](docs/research/scorecard.md)
- [Testing and release criteria](docs/TESTING.md)
- [License and distribution constraints](docs/LEGAL.md) and [third-party provenance](THIRD_PARTY.md)
- [GitHub issues](https://github.com/JaBoyAlex/mw3-recompiled/issues) and local `tasks/` catalog

Source/tool contributions are GPL-3.0-only unless a file says otherwise; see [LICENSE](LICENSE). Game code/data and vendor SDKs are excluded and carry their own rights. No affiliation with Activision, Infinity Ward, Sledgehammer, Microsoft, Valve or NVIDIA. No game download links or content are distributed here.
