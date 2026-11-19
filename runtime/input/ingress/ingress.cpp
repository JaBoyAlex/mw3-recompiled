// SPDX-License-Identifier: GPL-3.0-only
#include "input/ingress/ingress.hpp"

#include <limits>

namespace mw3::input {
namespace {
float stick(std::int16_t value) noexcept {
    return static_cast<float>(value) / (value < 0 ? 32768.0f : 32767.0f);
}
Frame normalized(const RawControls& value) noexcept {
    Frame frame{};
    frame.buttons = value.buttons;
    for (std::size_t i = 0; i < frame.axes.size(); ++i) frame.axes[i] = stick(value.sticks[i]);
    for (std::size_t i = 0; i < frame.triggers.size(); ++i) {
        frame.triggers[i] = static_cast<float>(value.triggers[i]) / 255.0f;
    }
    return frame;
}
Binding binding_for(std::uint64_t session, std::size_t slot, const SlotState& state) noexcept {
    return {session, slot, state.generation, state.owner, state.device};
}
} // namespace

IngressResult ControllerIngress::routed(Status status) noexcept {
    if (status == Status::ok) return {IngressCode::ok};
    return {IngressCode::routing_rejected, status};
}

IngressCode ControllerIngress::check_source(const DeviceToken& source) const noexcept {
    if (session_ == 0) return IngressCode::invalid_session;
    if (source.session != session_ || source.incarnation == 0 || source.device == 0) {
        return IngressCode::stale_source;
    }
    for (const auto& current : sources_) if (current == source) return IngressCode::ok;
    return IngressCode::stale_source;
}

Discovery ControllerIngress::discover(DeviceId device) noexcept {
    if (session_ == 0) return {{IngressCode::invalid_session}, {}};
    if (device == 0) return {{IngressCode::invalid_device}, {}};
    for (const auto& source : sources_) {
        if (source.device == device) return {{IngressCode::ok}, source};
    }
    for (auto& source : sources_) {
        if (source.device != 0) continue;
        if (incarnation_ == std::numeric_limits<std::uint64_t>::max()) {
            return {{IngressCode::incarnation_exhausted}, {}};
        }
        source = {session_, ++incarnation_, device};
        return {{IngressCode::ok}, source};
    }
    return {{IngressCode::capacity}, {}};
}

Join ControllerIngress::join(std::size_t slot, OwnerId owner, const DeviceToken& source) noexcept {
    const auto code = check_source(source);
    if (code != IngressCode::ok) return {{code}, {}};
    const auto attached = router_.attach(slot, owner, source.device);
    return {routed(attached.status), attached.binding};
}

IngressResult ControllerIngress::publish(const Binding& binding, const Observation& observation) noexcept {
    const auto code = check_source(observation.source);
    if (code != IngressCode::ok) return {code};
    if (observation.source.device != binding.device || observation.source.session != binding.session) {
        return {IngressCode::mismatched_source};
    }
    if ((observation.controls.buttons & ~known_controls) != 0) return {IngressCode::invalid_controls};
    return routed(router_.apply(binding, observation.sequence, normalized(observation.controls)));
}

IngressResult ControllerIngress::remove(const DeviceToken& source) noexcept {
    const auto code = check_source(source);
    if (code != IngressCode::ok) return {code};
    for (std::size_t i = 0; i < SlotRouter::slot_count; ++i) {
        const auto& slot = router_.slots()[i];
        if (slot.device != source.device) continue;
        const auto status = router_.disconnect(binding_for(session_, i, slot));
        if (status != Status::ok) return routed(status);
        break;
    }
    for (auto& current : sources_) if (current == source) { current = {}; break; }
    return {IngressCode::ok};
}

IngressResult ControllerIngress::restart() noexcept {
    if (session_ == 0) return {IngressCode::invalid_session};
    for (std::size_t i = 0; i < SlotRouter::slot_count; ++i) {
        const auto& slot = router_.slots()[i];
        if (slot.device == 0) continue;
        const auto status = router_.disconnect(binding_for(session_, i, slot));
        if (status != Status::ok) return routed(status);
    }
    sources_.fill({});
    return {IngressCode::ok};
}

std::size_t ControllerIngress::active_sources() const noexcept {
    std::size_t count = 0;
    for (const auto& source : sources_) if (source.device != 0) ++count;
    return count;
}

} // namespace mw3::input
