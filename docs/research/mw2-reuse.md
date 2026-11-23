# Reusing the MW2 port in MW3

The owner requests maximum useful reuse from
[PaulCombal/mw2-recompiled](https://github.com/PaulCombal/mw2-recompiled).
Prefer its compatible original C++ and tools when a concrete MW3 consumer needs
them. Preserve authorship/notices and adapt the smallest useful component to
the selected runtime and verified MW3 behavior. This avoids unnecessary parallel
implementations while retaining the project's correctness and delivery rules.

Reviewed November 22, 2026 for MW3-088. The public upstream HEAD still equals
our existing pin, `b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b`; the research
checkout is clean. No upstream pin or source/package is changed. The
[component manifest](../../config/reuse/mw2-components.json) records **16 areas,
55 source files, including 46 C++ headers/implementations**, with immutable
source links, SHA-256 identities, dependencies, intended consumers and required
validation. These are representative inspected components, not a claim that
every upstream line or transitive dependency has been audited.

This contribution is source inspection and adoption planning. **It integrates
no new upstream implementation**, executes no title, changes no SDK/runtime and
supplies no new performance result. Each subsequent port requires its own
bounded scope, live ownership claim and real consumer. The inventory explicitly
distinguishes existing adaptations, existing private research tools, candidates,
behavioral references and the unselected whole runtime.

## Work we already use

- [tools/disc.py](../../tools/disc.py) attributes the MW2 Python XDVDFS
  partition/directory-reader adaptation. MW3 adds its own bounded validation and
  content/executable identity. Keep the reviewed working reader; the upstream
  C++ ISO/folder abstraction is an installer candidate when needed.
- [mw2_tools.py](../../experiments/runtime-bakeoff/mw2_tools.py) prepares the
  pinned MW2-derived XenonRecomp/XenonAnalyse host-tool experiment privately,
  with exact patch/source identity. The analyzer is useful evidence. This does
  not mean its failed MW3 translator preflight or its runtime was selected.

The [existing runtime decision](../adr/0002-runtime-selection.md) retains actual
MW3 correctness failures: incompatible fixed heap/function-table ranges,
termination returning to the callback, and 377 SP / 436 MP switch-boundary errors
before title execution. Those findings concern the tested runtime/tool path;
they do not disqualify independent host utilities or erase useful MW2 work.
Keep one coherent repaired ReXGlue memory/context/thread model. This inventory
does not repeat the bakeoff, switch renderers or combine two kernels.

## Concrete reuse order

The manifest gives full file-level detail. Priority means relevance to a real
MW3 consumer, not a promise that a blocked milestone is ready or another lane
has been assigned work.

| Area | Concrete consumer | Adoption boundary |
| --- | --- | --- |
| Disc parser and C++ ISO/folder source | Existing MW3-002/045; future installer MW3-028 | Existing Python adaptation stays; consider C++ Source/UTF-8 code for a native installer, retaining bounded reads and immutable originals. |
| Patched analyzer/translator experiment | MW3-006/007/008/009 | Retain existing measured tool use and generic compiler-fix leads; MW3 configuration, switch recovery and selected-generator validation remain separate. |
| Cross-reference/object-use analyses | MW3-007/011/023 | Adapt generic scans to hash-bound MW3 metadata with bounded reads and clobber/unknown handling. MW2 addresses and inferred layouts are not inputs. |
| SDL discovery, diagnostics and rumble | **Next relevant implementation: MW3-083**, then MW3-012 | Prefer the useful host pieces through existing MW3-087 ingress and MW3-080 owners. The whole input module also depends on MW2 guest, guide/signin and renderer policy. |
| Parser-hardening checklist | MW3-020 | Use upstream bounds/sender/command-string fixes as initial audit leads; derive each MW3 function, structure, limit and regression case independently. |
| Windows/Linux metrics and reporting | MW3-005/013/032 | Reuse platform clock/memory sampling after agreeing a collector interface; adapt reports to our existing provenance schema and real MW3 frame/play boundaries. |
| Padding-free word-key hash | MW3-023, when a measured cache consumer exists | Small standard-library C++ candidate; preserve its no-padding type guard. It is a process-local hash, not a content/provenance digest. |
| Local settings/environment helpers | MW3-028/029 | Reuse precedence/loading structure with explicit option limits, validated numbers and complete secret redaction. No unused second configuration system is added. |
| SDL audio/XMA techniques | MW3-082/012/062 | Reuse isolated format/pacing/lifetime techniques behind the selected provider; preserve reviewed host ownership and XMA teardown repairs. |
| File/content/profile boundary techniques | MW3-081/012/060 | Reuse path/case-isolation ideas behind existing storage; retain the selected object/mount model and verify transactional saves and escape prevention. |
| Shader-cache marker/prewarm structure | MW3-011/023/028 | Reuse invalidation-before-build and device/driver matching with stronger content/config identity, after a real shader consumer exists. |
| C++ SPIR-V emitter/translator leads | MW3-006/011/023 | Isolate the emitter if justified. The translator depends on its own bindings/Xenos semantics; independently validate MW3 shaders rather than adding another permanent backend. |
| GPU timing and threaded recording | MW3-023/026/027 | Apply resource-lifetime and deferred timestamp techniques after faithful output and profiling. No recorder-thread speedup is assumed. |
| LAN/Steam/session admission | MW3-019/020/021/022 | Reuse bounded protocol techniques under the agreed MW3 identity/admission model and service authorization. No production service is contacted here. |
| Child launch, packages and setup | MW3-028/029 | Prefer portable SDL process and read-only content abstractions; adapt title identity and add deadlines, rollback and release-manifest checks. Launcher-specific work remains deferred to packaging. |
| Whole runtime/context/scheduler | MW3-008/010; protected MW3-046 | Remains unselected under existing measured failures. A future pivot needs a separate correctness/licensing comparison and migration plan. |

## Adaptations the inspected source requires

These are source observations, not newly executed failure or compatibility tests.
The manifest identifies each exact file and the tests needed before adoption.

**Cache identity.** Upstream `shader_marker.cpp` includes build, device, driver,
pipeline-cache UUID and scale. Its game-file records use name, size and modified
time; `SameTarget` intentionally omits file lines. That is insufficient for our
exact content/executable/configuration binding. A port must include cryptographic
content identities, translator/config versions and selected-backend compatibility.
Its negative tests must change content while preserving name, size and timestamp,
and reject stale, partial, corrupt or incompatible cache output.

**Settings.** `env.h` uses `strtoull`/`strtod` without complete parse/range checks.
`settings.cpp` imports prefixed variables, preserves an existing environment value
and hides names containing PASSWORD in its returned log. Preserve useful
precedence behavior, but add a bounded explicit option contract, numeric and
setter-error validation, and redaction for every supported secret category.
Do not let a shared `.env` override a lane's isolated profile or diagnostics.

**Process ownership.** The SDL spawn helper correctly accounts for missing
inherited Windows streams and passes an argument vector/environment. The helper
alone supplies no bounded wait/kill/reap protocol. A consumer must own its child,
deadline, output, exit status and cleanup; it must not stop another lane's run.

**Input ownership.** The inspected input code has useful SDL enumeration and
rumble handling, but also guest serialization, sign-in, guide/friends and player
diagnostics. Reuse the host pieces behind our existing explicit routing model.
Physical disconnect/reconnect, held controls, mapping, rumble cancellation and
late readings require actual owned hardware evidence; virtual tests remain a
separate evidence class. Do not replace already repaired sampling or assign
players by discovery order merely to match an upstream convenience policy.

**Graphics and security.** Upstream resource lifetimes, asynchronous recording,
shader binding assumptions and parser patches belong to a specific port.
Use them as implementation/test leads. Verify the selected backend, actual MW3
guest layouts and valid/invalid behavior before importing code or making a
performance, safety, frame or gameplay claim. Neither a source comment's timing
nor an MW2 security fix is an MW3 measurement.

## Licensing and provenance

The root [GPL-3.0 license](https://github.com/PaulCombal/mw2-recompiled/blob/b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b/LICENSE)
has SHA-256
`230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`.
The pinned README applies GPL-3.0-only to the project's own host code, tools,
patches and build files, and excludes game code/data and generated title C++.
Our public host code is also GPL-3.0-only. Retain upstream attribution, copyright,
license and modification notices for actual adaptations, reviewing each file
and transitive component instead of inferring a grant from GitHub language or
the root badge.

The map converter has distinct notices for other projects/tables and is excluded
from this adoption scope. MW3 PC game files remain optional. Steam/NVIDIA vendor
SDKs, game bytes, generated/decompiled title source, console keys and proprietary
artifacts are not copied or relicensed by this inventory. MW2's documented
Spacewar/AppID480 path grants no MW3 production authorization. No SDK/DRM or
anti-cheat bypass or update acquisition is performed.

The existing [distribution disposition](../legal/distribution.md) still governs
GPL host code combined with game-derived objects. Compatible host-source reuse
does not clear a game-linked binary release; ownership of a disc, dynamic linking
or public repository visibility supplies no missing permission. This records an
engineering source-reuse policy, not independent legal clearance.

## Reproduction, review and completion

The task was scoped separately in PR 123 before implementation. Serialized claim
run `45091269566` at `89375fe081a2613ea167ba83dc1f6fb83205cab1` assigned
issue 124 to the owner; dependency catalog states and remote closure were checked
by the workflow. The worktree/branch is `codex/MW3-088-mw2-reuse`; MW3-046 and
all other runtime, SDK, input and renderer reservations are untouched.

```text
git -C UPSTREAM rev-parse HEAD
git -C UPSTREAM status --porcelain
git ls-remote https://github.com/PaulCombal/mw2-recompiled.git HEAD
python tools/project.py list --ready --query MW2
python tools/project.py prompt MW3-088
python tools/project.py validate
python tools/check.py --config Release
git diff --check
```

Rehash the 55 listed source files and LICENSE against the pinned clean checkout,
check every immutable source URL and unique component ID, and resolve every
consumer task against the catalog. The manifest's public SHA-256 values are
metadata; raw game/SDK/trace data is not present. A separate re-read validates
the inventory, current identities and referenced paths, with meaningful modified
hash/duplicate ID/missing-task counterexamples rejected by that review procedure.

Local Windows Release checks: 277 Python tests with eight existing skips, parser
CTest 1/1, 63-task DAG, repository artifact heuristic and diff checks. The PR
records the exact final-head public Windows/Linux Debug/Release and sanitizer
matrix. This research-only change adds no parser/runtime implementation or new
test that merely duplicates metadata; no new SDK, GPU or title suite is needed.

Review is owner self-review, not an independent reviewer. Actual component ports,
full transitive provenance, hardware integration, comparative performance and
game-linked distribution remain separate required work. This task completes a
bounded reusable-source map and priority decision; it does not complete any of
those consumers or pass a service, title, mode, split-screen or gameplay gate.
