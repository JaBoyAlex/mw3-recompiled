# Distribution decision — MW3-031, 2026-11-19

**Use reviewed project source and developer-local builds as the current
delivery route. Keep game-linked binaries and generated title material out of
distributed packages.** This is the owner/lead's engineering disposition under
the existing licenses and unresolved rights, not a grant of game rights or
approval of an installer, Steam release or RecompLauncher package.

MW3-031 completes this scoped delivery decision and manifest review. It does
not clear the binary/package holds below or pass the release gate. Private
runtime development can continue without waiting for those separate release
decisions. No upstream license, existing project license or architecture is
changed by this document.

## What is actually combined

The [prior component assessment](runtime-and-distribution-assessment.md)
records exact upstream pins and file-level findings. The current public
project tools and native host probes are GPL-3.0-only. ReXGlue's root is
BSD-3-Clause, its host code generator includes a GPL decoder, and selected
runtime components include LGPL libraries. The BSD notices on our isolated
SDK patches apply to those patches, not to the GPL host probes or all of the
SDK's dependencies.

This is a concrete linking issue. The maintained
[`runtime/bringup/CMakeLists.txt`](../../runtime/bringup/CMakeLists.txt) builds
generated title sources into the `guest` object library, then links `guest`
and `rex::sdk` into the GPL host probe. The earlier
[entry-probe build](../../experiments/runtime-bakeoff/rexglue-host/CMakeLists.txt)
has the same basic edge. A final runtime-only dependency graph has not been
cleared for release. Replacing the old MW2 runtime with a BSD SDK does not
remove the host program's GPL terms, game copyright, or transitive obligations.

For a conveyed GPL combination, the license requires the applicable whole-work
licensing and corresponding-source arrangements; see local [GPLv3 sections
5–6](../../LICENSE). The game-derived guest objects cannot simply be declared
GPL by this project's owner. Omitting the ISO/assets from an executable still
leaves translated game logic and potentially copied generator/runtime material
in that executable. We have no recorded permission to convey that material on
the required terms. **That combined executable stays on hold.**

The FSF distinguishes use of a GPL generator from copyrightable material copied
into its output. Its [tool-output FAQ](https://www.gnu.org/licenses/gpl-faq.html#GPLOutput)
does not settle the separate game's rights. Our engineering conclusion is to
retain actual generated C++/objects privately and review their provenance and
link graph before considering distribution. Header-only glue, dynamic linking,
IPC, a loader or separately downloaded files do not establish a general
exception. No successful stub or technical protection bypass is part of this
delivery plan.

For LGPL libraries, the relevant license version and selected configuration
control the obligations. [LGPL 2.1 section 6](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html)
provides conditions for conveying a linked executable, including modification
and relinking arrangements under the chosen option. The current static
libmspack/FFmpeg build needs an actual plan for those requirements; notices
alone do not supply it. A plan that requires distributing title object files
cannot assume permission to do so. FFmpeg's own
[guidance](https://ffmpeg.org/legal.html) calls for exact matching library
source, configuration and changes, and distinguishes optional GPL components.
We retain the exact file/version findings from MW3-003 rather than treating
every fork/configuration as LGPL-only.

## Complete planned source manifest

The reviewed baseline is commit
`95332f34981b8767f49f757ac347633a71f6464c`. All **224 tracked files** are
assigned exactly once below. The private path/size/SHA-256 inventory receipt is
`4e7c7ef1dc43d741a7d967493d412058bc3d5c336e18b8844ea4a8d81cdb41fe`.
This document adds one source-document entry to that baseline; its task JSON
update changes an existing entry. Counts describe this snapshot, not an
automatic approval of every future file or commit.

| Group | Baseline count | Complete path rule | Source-package treatment |
| --- | ---: | --- | --- |
| Root | 9 | `.gitattributes`, `.gitignore`, `AGENTS.md`, `CMakeLists.txt`, `CMakePresets.json`, `CONTRIBUTING.md`, `LICENSE`, `README.md`, `THIRD_PARTY.md` | Retain license, attribution, build and contributor records |
| Contributor/CI metadata | 8 | All tracked `.agents/**` and `.github/**` | Original instructions/templates/workflows only; action pins are references, not bundled action executables or credentials |
| Maintained game-free source | 58 | All tracked `cmake/**`, `include/**`, `src/**`, `tools/**`, `tests/**` | GPL-3.0-only source and original synthetic fixtures; preserve `tools/disc.py`'s pinned GPL adaptation attribution |
| Preparation/host experiments | 74 | All tracked `config/**`, `runtime/**`, `experiments/**` | Source, recipes, hashes, original fixtures and reviewed patches only; preserve every narrower patch notice/license |
| Documentation/evidence/catalog | 75 | All tracked `docs/**`, `qa/**`, `tasks/**` | Reviewed text and synthetic/reference metadata; executable fingerprints are identities, not redistributed game bytes |

The preparation group includes the BSD repair patches with their
[memory notice](../../config/toolchains/rexglue-memory/NOTICE.md),
[stop notice](../../config/toolchains/rexglue-stop/NOTICE.md),
[Windows notice](../../config/toolchains/rexglue-windows/patches/NOTICE.md)
and [host-range notice](../../experiments/runtime-bakeoff/patches/NOTICE.md).
Those notices and
[`LICENSE.rexglue`](../../experiments/runtime-bakeoff/patches/LICENSE.rexglue)
must travel with them. Their GPL preparation/test drivers retain their own
license. REA is referenced by pinned archives/source, not vendored here; its
distribution and Ghidra/JDK/Node remain operator-supplied as documented in the
[evaluation](../research/rea-evaluation.md).

An eligible project source export contains only the reviewed tracked snapshot,
its licenses/notices and build instructions. It contains **no** `.git` history,
ignored/untracked files, `.local`, `out`, build/cache directories, upstream
checkouts, generated guest outputs, console keys, game files, vendor SDKs,
private receipts/traces, credentials, personal profiles or saves. A GitHub
source archive or `git archive` only selects tracked paths; it is not a
provenance/license audit. Re-evaluate new files before publishing a later
snapshot, and do not archive an entire working directory or installation.

## Complete planned binary and companion manifest

No binary package is created or approved by this task. These entries exhaust
the currently intended artifact classes, including files that must be absent.
A later release must replace every candidate class with explicit paths,
SHA-256/size, producer/build/config identity, license/notice/source disposition,
dependency edges and a clearance result. Unknown entries are excluded.

| Artifact class | Current package disposition | Required treatment before conveying it |
| --- | --- | --- |
| Standalone `mw3-xex-inspect` and original game-free tools | Candidate separate tooling release; no binary published here | Exact GPL source/build scripts, notices and compiler/runtime dependency disposition. The root CMake target links only the original metadata library; this is not a game launcher |
| Synthetic test/oracle/conformance runners | Developer-local by default | Separate original game-free runners from any SDK-linked or generated-title runner; test-only status does not remove linked-library obligations |
| Host generators/analyzers and generic SDK libraries | Private/operator-built; no bundled tool/SDK binaries | GPL decoder and LGPL/static dependencies, source/relink materials, file provenance and embedded-key disposition must be reviewed for the actual build |
| Title-linked probes, future launcher/game executable, shared libraries and guest objects | **Hold; exclude** | Game rights, host GPL combination, copied output/templates, exact runtime graph and all transitive terms must be resolved together |
| Original ISO/XEX/assets/updates/DLC, translated source, extracted images, shaders and derived shader/pipeline caches | **Exclude** | No recorded redistribution grant; ownership or device-specific cache generation is not that grant. User inputs stay unchanged and private |
| Steamworks headers, SDK tools, runtime API DLLs, app/service configuration | **Hold; exclude** | MW3-019 authorization, exact SDK agreement and designated redistribution rights. Public transport code does not grant an AppID or SDR service access |
| NVIDIA feature DLLs/SDKs, wrappers, Nsight/developer tools | **Hold; exclude** | Applicable feature agreement, specifically designated files, provenance and compatibility with the actual GPL combination; Streamline's framework license does not cover all feature binaries |
| Compiler, Windows/Vulkan/DXC tooling, CRT and platform driver/support components | Operator prerequisites; no wholesale bundling | For any future packaged runtime prerequisite, identify the actual permitted redistributable/version/notices. Do not copy an installed SDK or driver directory |
| Corresponding source, patch sets, object/relink materials, license/NOTICE texts and SBOM | Required companions where applicable; source must itself be distributable | Bind to the exact binary/configuration and provide the applicable source/replacement method. An SBOM or a link to a moving branch does not supply missing rights or exact source |
| PDB/DWARF, maps, crash reports and generated analysis outputs | Private by default | Check for game-derived code, embedded paths/data and secrets; only independently cleared game-free diagnostics can join a tooling package |
| Saves/profiles, settings with secrets, network captures/tokens, raw logs and dumps | **Exclude** | Isolated writable user state and private evidence never enter a distributable payload |
| Installer/updater/RecompLauncher metadata, icons and screenshots | Deferred to packaging work; no payload or manifest now | Actual allowlisted artifact set, rights in branding/media, verified install/rollback/update behavior and launcher compatibility |

Valve's [open-source guidance](https://partner.steamgames.com/doc/sdk/uploading/distributing_opensource?l=english)
warns about Steamworks/copyleft combinations and places distribution-rights
responsibility on the application operator. This supports retaining the
Steamworks hold; it is not a conclusion that every GPL application is banned
from Steam. No account agreement is accepted or application identity selected
here. The [existing SDK assessment](runtime-and-distribution-assessment.md#steamworks-and-nvidia-boundaries)
retains the exact NVIDIA/Steam distinctions and pinned license references.

## Source/local-build delivery route and remaining work

1. Publish only a separately reviewed source snapshot with the notices above.
   Developers install their own reviewed host prerequisites. The current public
   C++20 metadata build and synthetic tests require no game or proprietary SDK.
2. Private research requires operator-provided unchanged supported SP/MP inputs.
   Run the existing fingerprint guard, keep inputs read-only, and use a private
   cache/profile for every lane. A source recipe neither supplies game content
   nor decides the legal status of using it in every jurisdiction.
3. Where the operator has the applicable rights, build pinned host tools and
   the selected SDK locally with their exact transitive sources/configuration
   and reviewed patch composition. Keep the GPL host generator, runtime inputs
   and generated output identities distinct in the receipts.
4. Generate and compile title outputs locally, bind them to exact input hashes
   and recipe/tool versions, and retain them privately. Never upload a failed
   build archive or cache as a support convenience. No title-linked artifact is
   part of the source download or a shared prebuilt cache.
5. Optional Steam/NVIDIA SDK paths remain unavailable until the relevant owner
   authorization and feature tasks resolve them. They are not silently replaced
   by another game's AppID, an unauthorized SDK mirror or a claim that optional
   linking removes the current compatibility questions.

This choice has real installation costs: the private SDK requires a separate
C++23-capable toolchain while public game-free code is C++20; dependency
preparation, Windows/Linux SDK profiles, multiple private caches and local
generation are developer workflows, not a consumer installer. Disk/build-time
budgets, recoverable extraction, compiler/runtime prerequisites, cold/warm
generation behavior, permissions failures, cancellation, resume, update
invalidation and support diagnostics need installer evidence. Current bounded
startup is not a playable application for an installer to launch.

The requested easy RecompLauncher delivery remains a goal. Per the roadmap,
investigate the owner's Mojo! Recomp workflow when installer/release work
begins; no launcher research, integration or new package format is introduced
here. Packaging/source-service design work must not claim it makes unresolved
rights disappear.

## Unresolved permissions and accountable owner

The project owner/lead **JaBoyAlex** owns each decision below, obtaining the
relevant permission or review from the applicable rights holder where needed.
Maintainers can supply technical evidence; they cannot grant third-party
rights. These are tracked dispositions, not completed task dependencies.

| Record | Evidence needed to remove the hold | Existing work that owns the follow-through |
| --- | --- | --- |
| DIST-01: game-derived distribution | Explicit applicable permission/rights analysis for generated source, objects, shaders and combined binaries | Owner release decision with MW3-029; remains unresolved |
| DIST-02: actual license/link combination | Selected file graph, all copyright grants, host GPL treatment and any valid additional permissions; no blanket relicensing of existing code | Owner plus runtime/feature implementation records and final release review |
| DIST-03: selected SDK provenance | Resolve `thirdparty/pe/pe_image.h`'s recorded grant gap; inspect selected DXBC/DXC/STB and bundled/transitive code; retain all exact notices | Owner, building on MW3-003 component inventory; unresolved until package-specific review or an independently authored replacement |
| DIST-04: LGPL/source/relink route | Exact static component configurations, corresponding source/changes, applicable replacement/relink arrangement and rights in anything that arrangement distributes | Owner release manifest review in MW3-029 |
| DIST-05: Steam authorization | Authorized account/AppID/SDK access, applicable agreement and permitted selected redistributables/service access | MW3-019, then actual networking/relay acceptance; no borrowed identity |
| DIST-06: proprietary graphics features | Per-feature SDK/license version, designated files, applicable permissions and GPL compatibility disposition | MW3-023–026 and owner release review; no feature rights presumed |
| DIST-07: actual package contents | Explicit hashed source/binary/companion manifest, prerequisite rights, source offers, SBOM, installer/rollback/reproducibility evidence | MW3-029; RecompLauncher compatibility verified during packaging |

If the desired final binary/SDK combination cannot be cleared under current
licenses, the owner must choose among obtaining valid additional grants,
independently implementing a suitably licensed replacement, or an explicitly
accepted product limitation. None of those changes is made speculatively by
this task or by the parallel runtime lane. Until then, the source/private-build
route above is the selected engineering plan, with its own unresolved legal
questions recorded rather than labelled cleared.

## Validation boundary

Reviewed the complete tracked source candidate set, root inspector and actual
guest/SDK host link recipes, existing component evidence, all four current SDK
patch notice groups, and every planned binary/companion class above. Negative
manifest decisions explicitly exclude title objects, broad SDK/working-tree
archives, proprietary feature packages, private state and unknown artifacts.
They prevent a claim of clearance; they are not a new automated packager.

Primary license texts/guidance were consulted on 2026-11-19 (GNU web opens
timed out; the repository's complete GPL text and available FSF search material
were used alongside the existing pinned component evidence). Windows
`python tools/check.py --config Release` passes 114 Python tests with five
explicit tool/privilege skips (LLVM assembler/objcopy and four symlink cases),
and native CTest 1/1. The complete source category counts, relative links,
two-file scope and inventory receipt binding were checked. Normal GitHub CI
supplies the Windows/Linux and sanitizer matrix for this change; no game,
SDK, GPU or main-instance validation run is needed or claimed.
No package, binary upload, legal opinion, rights-holder permission, SDK
authorization or gameplay result is produced. Review is recorded as owner
self-review; no independent reviewer is represented.
