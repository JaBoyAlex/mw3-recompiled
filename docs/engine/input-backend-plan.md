# Selected input backend prerequisite

MW3-083 remains open and now depends on the bounded MW3-084 investigation.
The selected private SDK already provides SDL3 and Windows XInput drivers;
its SDL3 source pin is `147a8ee32dbf9ac02f3794964490687b6bbda1bc`
(headers report 3.4.14). Reuse and measure the existing provider before
introducing a parallel backend or assigning guest input services.

MW3-084 owns original virtual-device diagnostics in
`tests/host_platform/sdk_input`, its standalone driver
`tools/test_sdk_input.py`, and `docs/engine/sdk-input.md`. It loads the real
private provider/SDL libraries through reviewed SDK interfaces. It owns no SDK
source/profile, guest import allowlist, generated code, runtime model, backend
or shared test-discovery file. Active allocation 046 and filesystem 060 lanes
retain their current reservations and private resources.

Virtual controllers are original synthetic inputs confined to each diagnostic
process. No physical device is assigned, vibrated, detached or reconfigured.
The fixture must identify its own devices explicitly and fail on unexpected
enumeration rather than change external device state. All event dispatch,
handles and output directories belong to the lane. Any detected SDK defect
gets a separate agreed task before a patch; a diagnostic finding can be a
completed investigation while the physical integration remains blocked.

The raw SDL3 driver's device IDs and PadState values are not the SDK's four
user assignments or the MW3-080 owner reservations. In particular, the SDK
documents a neutral user-0 fallback and an optional shared-pads setting;
neither is proof of independent local players. Record these boundaries, actual
normalization, failure behavior and identities rather than guessing MW3 guest
semantics or treating a successful Initialize call as evidence of input.

MW3-083 still requires four real distinguishable controllers and supported
platform captures. The current host device inventory does not establish that
hardware evidence. Virtual-device success does not complete it, the parent
platform gate, original split-screen parity or four-player Survival. This
planning task adds no runtime behavior or performance claim.
