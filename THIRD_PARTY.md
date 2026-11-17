# Third-party provenance

Pinned research revisions/license digests are in `config/upstreams.lock.json`. Research clones under `.local/upstreams` are excluded from this repository. No console runtime, vendor SDK, game executable/data, translated game code or proprietary DLL has been vendored.

| Component | Use here | License/source disposition |
| --- | --- | --- |
| PaulCombal/mw2-recompiled `tools/xdvdfs.py` | Directory layout/probing adapted in `tools/disc.py` with additional validation | GPL-3.0-only, attributed in that file; upstream commit b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b |
| GNU GPL v3 text | Project license document | Verbatim standard license text |
| Synthetic fixtures/tests | Original project code/data, generated in memory | GPL-3.0-only; no extracted game bytes |
| Other upstreams | Source/documentation research only | No incorporation yet; adopting any code requires its notices and transitive audit |

The lock records top-level license evidence, not a completed transitive license audit. See docs/LEGAL.md before runtime/SDK adoption or distribution.

The [MW3-003 runtime/distribution assessment](docs/legal/runtime-and-distribution-assessment.md) compares pinned build edges, GPL host decoder code, LGPL runtime dependencies, vendor SDK restrictions and artifact delivery dispositions. [Component evidence](docs/legal/rexglue-components.json) records ReXGlue's 15 declared submodule pins and root/header license sources; it is not a final release SBOM. The BSD/MIT root licenses do not relicense GNU decoder code, LGPL libraries, Microsoft-derived PE declarations or proprietary NVIDIA/Steamworks materials. Runtime/game-linked binaries and SDK packages remain unapproved for release.
