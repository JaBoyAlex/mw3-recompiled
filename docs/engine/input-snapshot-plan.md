# Isolated initial input snapshot repair

MW3-085 reproduces an initial-held-input failure in the selected SDK on native
Windows and Linux/WSL, including the supported sanitizer profiles. In the
controlled case SDL reports an original virtual pad's button held and X=3072,
but SDK user 0, assigned that pad, reports button=0 and X=0 after discovery and
another event pump. Established-device routing passes; the initial-held case
remains a failed correctness assertion. It is not converted into a PASS.

MW3-086 scopes the repair separately and blocks physical input integration 083
until its evidence is reconciled. It depends on completed 084/085 so their
runner paths cannot be edited in parallel with those investigations. Before
claiming, check live ownership, source/patch provenance and the exact current
baseline, including any later upstream fix. Do not infer this plan assigns work.

The proposed boundary is provider snapshot initialization, not guest input
admission or a replacement assignment framework. Review creation/event ordering,
SDL current-state APIs, normalization and permitted threads before changing
code. Keep the original held-discovery assertion and raw SDL values as the
regression control. A broader finding gets another agreed task.

The new profile must use its own derived source tree, build, lock, receipt,
package and diagnostic outputs. Existing XMA, allocation and audio SDKs are
inputs, not writable workspaces. Reserve only
`config/toolchains/rexglue-input-snapshot`, the new preparation tool, explicit
profile admission in the two completed input runners, its own guard tests and
subsystem evidence. Replace only reviewed provider artifacts and explicitly
identified matching sidecars; keep every unaffected parent file/hash intact.

The main instance retains allocation 046 and host-audio 061. This planning PR
changes no SDK or runtime source, process, profile, test namespace or guest
allowlist. Physical controllers, independent hardware and actual title input
remain unverified even after a host snapshot repair. No playable boot,
split-screen, Survival extension, title performance or distribution claim is
implied.
