# Platform work after the scoped kernel checkpoint

MW3-012 remains open. This owner/lead split makes bounded work available
without claiming audio, controllers, saves or gameplay already function.
The active allocation-import lane (046) and shared runtime/SDK interfaces are
untouched. The first-frame epic (011) still needs its own scoped children.

| Task | Scope | Evidence boundary |
| --- | --- | --- |
| 080 | Original four-slot host ownership model | Game-free correctness only; no physical device or guest mapping |
| 081 | Isolated profile/save storage primitives | Host confinement/recovery only; no MW3 save-format compatibility |
| 082 | Selected audio output and title playback after 011 | Requires actual title capture/listening and underrun/soak evidence |
| 083 | Physical controller backend after 080 | Requires four real devices; no inferred guest input or gameplay parity |
| 012 | Final platform evidence reconciliation | Requires real title behavior; no completion by implementing a description |

IDs 080–083 reserve this disjoint platform group while leaving the kernel
lane's next sequential repair IDs free. Task numbers do not imply priority or
maturity. Current GitHub ownership and serialized task-admin claims still
govern availability. Never assign a child just because this table names it.

## Ownership/model contract for 080

This is an original C++20 fixed-capacity component, not another runtime or an
input emulation framework. Four host slots are a routing capacity, not a newly
verified retail player limit. Local owner IDs are opaque bindings, not account
authentication or profile files. Device IDs are opaque backend identities.

The host explicitly reserves an owner and attaches a device; enumeration
order cannot silently choose a player. A device or owner cannot occupy two
slots. Another device cannot take over an occupied slot. Disconnect makes
all input neutral and retains local-owner reservation until explicit release.
Session/binding tokens and monotonically ordered samples reject late input
after disconnect, reassignment or another session. Frames must be validated
before changing any slot. Queries and rejected operations leave unrelated
slots unchanged.

The model is owned by one polling thread. It defines no threading, scheduler,
SDL/XInput, Xbox-account, guest-address or SDK service contract. A later backend
depends on the accepted 080 interface; it does not edit it during a parallel
implementation. New shared interface or guest binding work requires its own
agreed task. No root CMake/CI interface is changed by these children implicitly.

This planning split establishes the empty `tests/host_platform/__init__.py`
namespace (avoiding the Python standard-library `platform` name) so normal root test discovery can reach each child's package. It
remains lead-owned in 012. Input, storage, audio and backend children own their
distinct test subdirectories and must not edit that shared namespace file.
Each child has a standalone native test
project, private build outputs and process handles. Keep the two-worker host
build limit and do not run GPU/title suites over another lane's resources.

## What remains outside the foundation components

Storage work must keep prepared content and writable profiles distinct and
must retain damaged/partial data without overwriting original saves. Host
rollback does not establish proprietary save-format or guest filesystem
behavior. Audio work reuses the documented selected-runtime provenance rather
than assuming every transitive dependency is permissive. Existing XMA packet
teardown evidence is useful but does not prove audible playback or mixing.

Any guest input/save/audio import admission, SDK repair, frame hook or newly
discovered shared seam must be split and recorded before implementation.
Children do not enable all SDK services, guess MW2 guest addresses, change
generated game code or return success for unsupported work. The platform
gate requires those eventual title-level integrations and actual observations
even after host contracts pass; add their scoped follow-ups as they are audited.

Four physical inputs, original console split-screen and four-player Survival
are distinct evidence levels. Preserve original behavior and the requested
extension's fallback; none of these planning records or synthetic tests passes
the reference, gameplay, network, enhancement or release gates.
