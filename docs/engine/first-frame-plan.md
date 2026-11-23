# First-frame integration after initial heap startup

**No rendered MW3 frame, menu or playable mode is verified.** MW3-011 remains
an unfinished epic and must not be claimed as one implementation lane.
The immediate priority is a visible Windows Campaign boot and then one
controllable scene using the existing selected SDK and compatibility renderer.
Original modes and console split-screen remain product requirements.

## Verified foundations and current lane

MW3-046 accepts the scoped allocation/free import contracts with the MW3-091
safety profile. Child [MW3-092](title-allocation.md) executes the audited header
service and first 1 MiB reserve-only allocation, then stops before returning to
title code. That explicit checkpoint remains a regression.

Completed child [MW3-093](title-startup.md) extends the same isolated lifecycle
seam through the following 64 KiB commit and audited heap initialization to
the next `KeGetCurrentProcessType` call, which is not invoked. SP/MP acceptance
probes reach that boundary on native hosts and supported sanitizer profiles,
with separate artifact review. Its inspection mode stops before the commit.
Neither child completes first-frame epic 011.

Content preparation 045 supplies verified private full console content.
Native synthetic D3D12 bootstrap 050 and display-query contracts 051 are
complete foundations. They do not prove MW3 has loaded its assets or rendered
through those interfaces. The current startup probe remains headless and uses
the minimal two-XEX input directory.

## Next integration scope

Keep the existing header, first-allocation and new continuation checkpoints.
The next serial lead task must independently inspect original instructions and
data accesses following the observed service boundary, agree a bounded group
of service/caller/value/output contracts, publish scope and claim the shared
runtime paths through task-admin before extending execution. Prefer useful
startup segments using existing implementations; repair demonstrated MW3
mismatches rather than rebuilding a generic runtime.

Move toward content loading, device initialization and the existing renderer
as actual execution identifies those interfaces. Use the prepared private
content when the audited title path first needs it. Bind every admitted path
to exact executable, generation, metadata, compiler, SDK and configuration
identities. A related title's function name or address is only a hypothesis.

An intended result that disagrees with owned-title evidence blocks that
admission and gets a scoped investigation or SDK repair. Unknown services and
indirect targets remain diagnostic; do not enable the whole SDK table, force
success values, edit generated title code or bypass unavailable services.

Windows Campaign probes lead development. SP/MP and supported sanitizer/platform
checks, negative controls and complete thread/runtime/mapping recovery are
acceptance requirements at the completed integration boundary. WSL on the same
Windows machine is not independent hardware. Keep private inputs, generated
code, logs, outputs and profiles isolated; build with at most two workers and
serialize heavy runs. No gameplay benchmark, framework speed claim or calendar
playable date follows from these probes. See the
[boot-first integration/tool findings](../research/boot-acceleration.md).
