// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "input/slot_router.hpp"

namespace mw3::input {

// Original host identities, deliberately independent of SDK/Xbox button bits.
enum class Control : std::uint32_t {
    south = 1u << 0, east = 1u << 1, west = 1u << 2, north = 1u << 3,
    up = 1u << 4, down = 1u << 5, left = 1u << 6, right = 1u << 7,
    start = 1u << 8, back = 1u << 9, left_stick = 1u << 10,
    right_stick = 1u << 11, left_shoulder = 1u << 12,
    right_shoulder = 1u << 13, guide = 1u << 14,
};
constexpr std::uint32_t bit(Control control) noexcept { return static_cast<std::uint32_t>(control); }
inline constexpr std::uint32_t known_controls = (1u << 15) - 1;

struct RawControls {
    std::uint32_t buttons{};
    // Centered at zero, positive right/up. No second Y inversion or deadzone.
    std::array<std::int16_t, 4> sticks{};
    std::array<std::uint8_t, 2> triggers{};
};

struct DeviceToken {
    std::uint64_t session{};
    std::uint64_t incarnation{};
    DeviceId device{};
    bool operator==(const DeviceToken&) const = default;
};

struct Observation {
    DeviceToken source{};
    std::uint64_t sequence{}; // Host ordering within a binding, not an SDK packet number.
    RawControls controls{};
};

enum class IngressCode {
    ok, invalid_session, invalid_device, capacity, incarnation_exhausted,
    stale_source, mismatched_source, invalid_controls, routing_rejected,
};

struct IngressResult {
    IngressCode code{IngressCode::stale_source};
    std::optional<Status> routing_status{}; // Present only for routing_rejected.
    [[nodiscard]] bool ok() const noexcept { return code == IngressCode::ok; }
};
struct Discovery {
    IngressResult result{};
    DeviceToken token{}; // Valid only on success.
};
struct Join {
    IngressResult result{};
    Binding binding{}; // Valid only on success.
};

// A single polling thread owns all calls. SDK availability/policy is the caller's
// responsibility. The caller supplies a unique nonzero session across objects
// whose observations can intermix. Tokens detect stale input, not authentication.
class ControllerIngress final {
public:
    static constexpr std::size_t source_capacity = 16;
    explicit ControllerIngress(std::uint64_t session) noexcept : session_(session), router_(session) {}
    ControllerIngress(const ControllerIngress&) = delete;
    ControllerIngress& operator=(const ControllerIngress&) = delete;
    ControllerIngress(ControllerIngress&&) = delete;
    ControllerIngress& operator=(ControllerIngress&&) = delete;

    [[nodiscard]] Discovery discover(DeviceId device) noexcept;
    [[nodiscard]] Status reserve(std::size_t slot, OwnerId owner) noexcept { return router_.reserve(slot, owner); }
    [[nodiscard]] Status release(std::size_t slot, OwnerId owner) noexcept { return router_.release(slot, owner); }
    [[nodiscard]] Join join(std::size_t slot, OwnerId owner, const DeviceToken& source) noexcept;
    [[nodiscard]] IngressResult publish(const Binding& binding, const Observation& observation) noexcept;
    [[nodiscard]] IngressResult remove(const DeviceToken& source) noexcept;
    [[nodiscard]] IngressResult restart() noexcept;
    [[nodiscard]] std::size_t active_sources() const noexcept;
    [[nodiscard]] const auto& slots() const noexcept { return router_.slots(); }
    [[nodiscard]] std::optional<SlotState> state(std::size_t slot) const noexcept { return router_.state(slot); }

private:
    [[nodiscard]] IngressCode check_source(const DeviceToken& source) const noexcept;
    static IngressResult routed(Status status) noexcept;
    const std::uint64_t session_;
    SlotRouter router_;
    std::array<DeviceToken, source_capacity> sources_{};
    std::uint64_t incarnation_{}; // Never reset by a backend restart or device removal.
};

} // namespace mw3::input
