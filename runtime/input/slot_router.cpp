// SPDX-License-Identifier: GPL-3.0-only
#include "input/slot_router.hpp"

#include <cmath>
#include <limits>

namespace mw3::input {
namespace {
bool valid_frame(const Frame& frame) noexcept {
    for (float value : frame.axes) {
        if (!std::isfinite(value) || value < -1.0f || value > 1.0f) return false;
    }
    for (float value : frame.triggers) {
        if (!std::isfinite(value) || value < 0.0f || value > 1.0f) return false;
    }
    return true;
}
void neutralize(SlotState& slot) noexcept {
    slot.device = 0;
    slot.last_sequence = 0;
    slot.frame = {};
}
} // namespace

Status SlotRouter::check_slot(std::size_t slot) const noexcept {
    if (session_ == 0) return Status::invalid_session;
    if (slot >= slot_count) return Status::invalid_slot;
    return Status::ok;
}

Status SlotRouter::check_binding(const Binding& binding) const noexcept {
    const auto status = check_slot(binding.slot);
    if (status != Status::ok) return status;
    const auto& slot = slots_[binding.slot];
    if (binding.session != session_ || slot.device == 0 ||
        binding.generation != slot.generation || binding.owner != slot.owner ||
        binding.device != slot.device) return Status::stale_binding;
    return Status::ok;
}

Status SlotRouter::reserve(std::size_t index, OwnerId owner) noexcept {
    const auto status = check_slot(index);
    if (status != Status::ok) return status;
    if (owner == 0) return Status::invalid_identity;
    auto& slot = slots_[index];
    if (slot.owner != 0 && slot.owner != owner) return Status::slot_occupied;
    for (std::size_t i = 0; i < slot_count; ++i) {
        if (i != index && slots_[i].owner == owner) return Status::duplicate_owner;
    }
    slot.owner = owner;
    return Status::ok;
}

AttachResult SlotRouter::attach(std::size_t index, OwnerId owner, DeviceId device) noexcept {
    const auto status = check_slot(index);
    if (status != Status::ok) return {status, {}};
    if (owner == 0 || device == 0) return {Status::invalid_identity, {}};
    auto& slot = slots_[index];
    if (slot.owner != owner) return {Status::wrong_owner, {}};
    if (slot.device != 0 && slot.device != device) return {Status::slot_occupied, {}};
    if (slot.device == 0) {
        for (const auto& other : slots_) {
            if (other.device == device) return {Status::duplicate_device, {}};
        }
        if (slot.generation == std::numeric_limits<std::uint64_t>::max()) {
            return {Status::binding_exhausted, {}};
        }
        ++slot.generation;
        slot.device = device;
    }
    return {Status::ok, {session_, index, slot.generation, owner, device}};
}

Status SlotRouter::disconnect(const Binding& binding) noexcept {
    const auto status = check_binding(binding);
    if (status != Status::ok) return status;
    neutralize(slots_[binding.slot]);
    return Status::ok;
}

Status SlotRouter::release(std::size_t index, OwnerId owner) noexcept {
    const auto status = check_slot(index);
    if (status != Status::ok) return status;
    if (owner == 0) return Status::invalid_identity;
    auto& slot = slots_[index];
    if (slot.owner != owner) return Status::wrong_owner;
    neutralize(slot);
    slot.owner = 0;
    // Retain generation so even the same owner/device cannot revive a token.
    return Status::ok;
}

Status SlotRouter::apply(const Binding& binding, std::uint64_t sequence,
                         const Frame& frame) noexcept {
    const auto status = check_binding(binding);
    if (status != Status::ok) return status;
    auto& slot = slots_[binding.slot];
    if (sequence == 0 || sequence <= slot.last_sequence) return Status::out_of_order;
    if (!valid_frame(frame)) return Status::invalid_frame;
    slot.frame = frame;
    slot.last_sequence = sequence;
    return Status::ok;
}

std::optional<SlotState> SlotRouter::state(std::size_t index) const noexcept {
    if (index >= slot_count) return std::nullopt;
    return slots_[index];
}

} // namespace mw3::input
