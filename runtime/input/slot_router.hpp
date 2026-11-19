// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace mw3::input {

using OwnerId = std::uint64_t;
using DeviceId = std::uint64_t;

// Original host values. No Xbox button bits, account IDs or guest layouts.
struct Frame {
    std::uint64_t buttons{};
    std::array<float, 4> axes{};      // Each finite and in [-1, 1].
    std::array<float, 2> triggers{};  // Each finite and in [0, 1].
    bool operator==(const Frame&) const = default;
};

enum class Status {
    ok,
    invalid_session,
    invalid_slot,
    invalid_identity,
    wrong_owner,
    slot_occupied,
    duplicate_owner,
    duplicate_device,
    stale_binding,
    invalid_frame,
    out_of_order,
    binding_exhausted,
};

struct Binding {
    std::uint64_t session{};
    std::size_t slot{};
    std::uint64_t generation{};
    OwnerId owner{};
    DeviceId device{};
    bool operator==(const Binding&) const = default;
};

struct AttachResult {
    Status status{Status::stale_binding};
    Binding binding{};  // Valid only when status == ok.
};

struct SlotState {
    OwnerId owner{};   // Zero is unreserved.
    DeviceId device{}; // Zero is disconnected; owner remains reserved.
    std::uint64_t generation{};
    std::uint64_t last_sequence{};
    Frame frame{};
    bool operator==(const SlotState&) const = default;
};

// One polling thread owns this object and all calls. No internal locks or I/O.
// Caller supplies a nonzero session unique across routers whose events can mix.
// Tokens provide stale-event detection, not authentication or persistence.
class SlotRouter final {
public:
    static constexpr std::size_t slot_count = 4;
    explicit SlotRouter(std::uint64_t session) noexcept : session_(session) {}
    SlotRouter(const SlotRouter&) = delete;
    SlotRouter& operator=(const SlotRouter&) = delete;
    SlotRouter(SlotRouter&&) = delete;
    SlotRouter& operator=(SlotRouter&&) = delete;

    [[nodiscard]] Status reserve(std::size_t slot, OwnerId owner) noexcept;
    [[nodiscard]] AttachResult attach(std::size_t slot, OwnerId owner, DeviceId device) noexcept;
    [[nodiscard]] Status disconnect(const Binding& binding) noexcept;
    [[nodiscard]] Status release(std::size_t slot, OwnerId owner) noexcept;
    [[nodiscard]] Status apply(const Binding& binding, std::uint64_t sequence,
                               const Frame& frame) noexcept;
    [[nodiscard]] std::optional<SlotState> state(std::size_t slot) const noexcept;
    [[nodiscard]] const std::array<SlotState, slot_count>& slots() const noexcept { return slots_; }

private:
    [[nodiscard]] Status check_slot(std::size_t slot) const noexcept;
    [[nodiscard]] Status check_binding(const Binding& binding) const noexcept;
    const std::uint64_t session_;
    std::array<SlotState, slot_count> slots_{};
};

} // namespace mw3::input
