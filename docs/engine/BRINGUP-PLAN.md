# Kernel bring-up lanes after reproducible generation

Task 010 is an evidence gate, not an implementation claim. Tasks 036–041 split
its work before anyone claims it. None is completed by the runtime bakeoff or
by writing this plan. The parent still blocks first-frame work (011).

| Task | Work | Dependencies | Suggested owner |
| --- | --- | --- | --- |
| 036 | First read-only header service, used module-handle cell, guarded native harness | 009 | Lead |
| 037 | Actual selected-runtime memory/pointer/guard stress | 009 | Friend A or QA lane |
| 038 | Selected-translator original PPC differential oracle and exact-math cases | 009 | Friend B or CPU lane |
| 039 | Thread/wait/TLS/lifecycle stress and retained aggregate failures | 009 | QA lane after 037, or independent contributor |
| 040 | Native Windows SDK and guarded SP/MP execution | 009, 036 | Lead or Windows contributor |
| 041 | Controlled real-title checkpoint and orderly diagnostic shutdown | 036–040, 042 | Lead integration |
| 042 | Repair decommitted-page access; isolated SDK integration and regressions | 037, 040 | Lead runtime seam |

With two people, the lead takes 036/040 while the other developer selects 037
or 038, then 039. With three, start lead/036, developer 2/038 and developer
3/037; the QA lane can move to 039 afterward. More contributors can claim
disjoint ready scopes through task-admin. Each task JSON has its own prompt,
observable acceptance and negative checks; issue assignees define ownership.

Tests in the memory/CPU/thread lanes use standalone test projects and direct
selected SDK interfaces. They do not edit the first-import harness or shared
SDK patch. Agree any needed shared interface or SDK repair in a separate
scoped task before parallel implementation. Each lane has its own outputs,
profile, locks and process handles. On this machine, retain the two-worker
build budget and serialize expensive builds/runs; do not silently overwrite
SDK source-tree outputs. GPU tests still wait for their dependencies.

Memory task 037 has reproduced decommit failures on both hosts: checked read/
write APIs accept pages whose commit state is cleared, and a forbidden raw read
does not fault. Task 042 isolates the repair and shared preparation/cache seam;
041 explicitly depends on it. Building a regression harness completes no memory
correctness gate while these cases fail. Release mapping access is a separate
upstream setting (`runtime.protect_on_release`), not the same defect. Its explicit
strict profile faults correctly. No performance policy is selected by these tests.

The lead records this discovered blocker as a planning amendment to parent 010,
with its acceptance unchanged. The new task reserves shared SDK preparation only
after 037 is merged; no parallel worker may change that interface before agreement.

Task 036 must compare the first header query with an independent bounded
reader, validate the actually used module-handle pointer, and permit only that
reviewed read-only import. All other functions remain diagnostic stops. The
remaining data imports stay explicitly unaudited. A new reached import creates
an auditable follow-up, not permission to enable the SDK's entire service table.
No success-valued stub or guessed address can advance a checkpoint.

Tasks 037–039 distinguish native callbacks, translated synthetic instructions
and owned-title execution. Existing 51/21 service checks and the canonical 547
PPC checks are reusable evidence, not substitutes for untested guest pointers,
the selected translator's math path, stack guards or contention. Record both
held-out cases and deliberate incorrect-result/failure mutations.

The 010 gate requires all children plus real Windows/Linux title evidence and
orderly teardown. An intentional bounded diagnostic stop is labeled as such;
it is not successful game boot. Newly discovered services and platform defects
must be split into bounded tasks and added to the gate when needed. A completed
gate will not certify every kernel import or any original gameplay mode.
