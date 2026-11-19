// SPDX-License-Identifier: GPL-3.0-only
#include "input/ingress/ingress.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <type_traits>

using namespace mw3::input;
namespace {
unsigned checks{};
void check(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}
constexpr std::array<std::size_t, 4> slots{2, 0, 3, 1};
constexpr std::array<OwnerId, 4> owners{61, 17, 99, 8};
constexpr std::array<DeviceId, 4> devices{41, 7, 1001, 3};
RawControls controls(std::size_t pad) {
    return {1u << pad, {static_cast<std::int16_t>(pad * 8192), 32767, -16384, -32768}, {0, 255}};
}
struct Four {
    ControllerIngress ingress;
    std::array<DeviceToken, 4> tokens{};
    std::array<Binding, 4> bindings{};
    explicit Four(std::array<std::size_t, 4> order = {0, 1, 2, 3}, std::uint64_t session = 41) : ingress(session) {
        for (std::size_t slot = 0; slot < 4; ++slot) check(ingress.reserve(slot, owners[slot]) == Status::ok, "reserve failed");
        for (auto pad : order) {
            const auto found = ingress.discover(devices[pad]); check(found.result.ok(), "discovery failed");
            tokens[pad] = found.token;
            const auto joined = ingress.join(slots[pad], owners[slots[pad]], tokens[pad]);
            check(joined.result.ok(), "explicit owner join failed"); bindings[pad] = joined.binding;
        }
    }
    void send(std::size_t pad, std::uint64_t sequence = 1) {
        check(ingress.publish(bindings[pad], {tokens[pad], sequence, controls(pad)}).ok(), "publish failed");
    }
    void verify() {
        for (std::size_t pad = 0; pad < 4; ++pad) {
            const auto state = ingress.state(slots[pad]);
            check(state && state->owner == owners[slots[pad]] && state->device == devices[pad], "owner/device route changed");
            check(state->frame.buttons == (std::uint64_t{1} << pad) && state->frame.axes[1] == 1 &&
                  state->frame.axes[2] == -0.5f && state->frame.axes[3] == -1 &&
                  state->frame.triggers[0] == 0 && state->frame.triggers[1] == 1, "independent controls changed");
        }
    }
};

void normalization() {
    Four f;
    auto raw = controls(0); raw.buttons = known_controls;
    raw.sticks = {-32768, 32767, 0, -16384}; raw.triggers = {0, 255};
    check(f.ingress.publish(f.bindings[0], {f.tokens[0], 1, raw}).ok(), "edge publish failed");
    const Frame expected{known_controls, {-1, 1, 0, -0.5f}, {0, 1}};
    check(f.ingress.state(slots[0])->frame == expected, "normalization endpoints differ");
    raw.sticks = {-1, 1, 16384, -8192}; raw.triggers = {128, 1};
    check(f.ingress.publish(f.bindings[0], {f.tokens[0], 2, raw}).ok(), "intermediate publish failed");
    const auto frame = f.ingress.state(slots[0])->frame;
    check(frame.axes[0] < 0 && frame.axes[1] > 0 && std::abs(frame.axes[2] - 0.50001526f) < 0.0000001f &&
          frame.axes[3] == -0.25f && std::abs(frame.triggers[0] - 0.5019608f) < 0.0000001f &&
          frame.triggers[1] > 0 && frame.triggers[1] < 0.004f, "intermediate normalization differs");
    check(bit(Control::south) == 1 && bit(Control::up) == 16 && bit(Control::guide) == 16384, "original host controls changed");
}
void explicit_joins() {
    Four f({3, 1, 0, 2});
    for (std::size_t pad = 0; pad < 4; ++pad) f.send(pad);
    f.verify(); const auto before = f.ingress.slots();
    for (std::size_t pad = 0; pad < 4; ++pad) {
        check(f.ingress.discover(devices[pad]).token == f.tokens[pad], "connected discovery was not idempotent");
        const auto joined = f.ingress.join(slots[pad], owners[slots[pad]], f.tokens[pad]);
        check(joined.result.ok() && joined.binding == f.bindings[pad], "same join replaced binding");
    }
    check(f.ingress.slots() == before, "idempotent calls reset held state/sequence");
    auto changed = controls(2); changed.buttons = 0;
    check(f.ingress.publish(f.bindings[2], {f.tokens[2], 2, changed}).ok(), "changed input failed");
    for (std::size_t pad = 0; pad < 4; ++pad) {
        if (pad == 2) check(f.ingress.state(slots[pad])->frame.buttons == 0, "changed owner not updated");
        else check(f.ingress.state(slots[pad]) == before[slots[pad]], "one reading changed another owner");
    }
}
void rejected_mutations() {
    check(!Discovery{}.result.ok() && !Join{}.result.ok() && !IngressResult{}.ok(), "empty result reports success");
    Four f; for (std::size_t p = 0; p < 4; ++p) f.send(p);
    const auto before = f.ingress.slots();
    auto denied = [&](IngressResult result, IngressCode code) {
        check(result.code == code && f.ingress.slots() == before && f.ingress.active_sources() == 4, "rejection mutated routing");
    };
    auto unknown = controls(0); unknown.buttons |= 1u << 31;
    denied(f.ingress.publish(f.bindings[0], {f.tokens[0], 2, unknown}), IngressCode::invalid_controls);
    denied(f.ingress.publish(f.bindings[0], {f.tokens[1], 2, controls(1)}), IngressCode::mismatched_source);
    auto foreign = f.tokens[0]; ++foreign.session;
    denied(f.ingress.publish(f.bindings[0], {foreign, 2, controls(0)}), IngressCode::stale_source);
    auto stale = f.tokens[0]; ++stale.incarnation;
    denied(f.ingress.remove(stale), IngressCode::stale_source);
    auto bad = f.bindings[0]; ++bad.owner;
    const auto result = f.ingress.publish(bad, {f.tokens[0], 2, controls(0)});
    denied(result, IngressCode::routing_rejected); check(result.routing_status == Status::stale_binding, "routing detail lost");
    const auto joined = f.ingress.join(slots[0], owners[slots[0]] + 1, f.tokens[0]);
    denied(joined.result, IngressCode::routing_rejected); check(joined.result.routing_status == Status::wrong_owner, "wrong-owner detail lost");
    check(f.ingress.reserve(slots[0], 500) == Status::slot_occupied && f.ingress.slots() == before, "reservation stolen");
    check(f.ingress.discover(0).result.code == IngressCode::invalid_device && f.ingress.slots() == before, "zero source accepted");
    f.send(0, 2); // Rejected samples did not consume sequence 2.
    ControllerIngress disabled(0);
    check(disabled.discover(1).result.code == IngressCode::invalid_session &&
          disabled.remove(f.tokens[0]).code == IngressCode::invalid_session &&
          disabled.restart().code == IngressCode::invalid_session &&
          disabled.reserve(0, 1) == Status::invalid_session, "disabled ingress mutated");
}
void removal_reuse() {
    Four f; for (std::size_t p = 0; p < 4; ++p) f.send(p);
    const auto before = f.ingress.slots(); const auto old = f.tokens[1]; const auto binding = f.bindings[1];
    check(f.ingress.remove(old).ok(), "remove failed");
    const auto vacant = f.ingress.state(slots[1]);
    check(vacant && vacant->owner == owners[slots[1]] && vacant->device == 0 && vacant->frame == Frame{} && vacant->last_sequence == 0, "remove lost owner or held input");
    for (std::size_t p : {0u, 2u, 3u}) check(f.ingress.state(slots[p]) == before[slots[p]], "remove changed another owner");
    auto found = f.ingress.discover(devices[1]); check(found.result.ok() && found.token != old, "reused ID revived incarnation");
    auto joined = f.ingress.join(slots[1], owners[slots[1]], found.token); check(joined.result.ok(), "explicit rejoin failed");
    const auto next = f.ingress.slots();
    check(f.ingress.publish(joined.binding, {old, 2, controls(1)}).code == IngressCode::stale_source, "late source revived");
    check(f.ingress.publish(binding, {found.token, 2, controls(1)}).routing_status == Status::stale_binding, "late binding revived");
    check(f.ingress.remove(old).code == IngressCode::stale_source && f.ingress.slots() == next, "late removal stole replacement");
    check(f.ingress.publish(joined.binding, {found.token, 1, controls(1)}).ok(), "rejoin sequence did not restart");
    check(f.ingress.release(slots[1], owners[slots[1]]) == Status::ok && f.ingress.reserve(slots[1], 600) == Status::ok, "explicit release/reserve failed");
    const auto new_owner = f.ingress.join(slots[1], 600, found.token); check(new_owner.result.ok(), "new owner join failed");
    check(f.ingress.publish(joined.binding, {found.token, 2, controls(1)}).routing_status == Status::stale_binding, "old owner revived");
    check(f.ingress.publish(new_owner.binding, {found.token, 1, controls(1)}).ok(), "new owner publish failed");
}
void backend_restart() {
    Four f; for (std::size_t p = 0; p < 4; ++p) f.send(p);
    check(f.ingress.restart().ok() && f.ingress.active_sources() == 0, "restart did not clear sources");
    for (std::size_t slot = 0; slot < 4; ++slot) {
        const auto state = f.ingress.state(slot);
        check(state->owner == owners[slot] && state->device == 0 && state->frame == Frame{}, "restart released owner or retained input");
    }
    for (std::size_t p = 0; p < 4; ++p) {
        const auto found = f.ingress.discover(devices[p]); check(found.result.ok() && found.token != f.tokens[p], "restart reused token");
        const auto joined = f.ingress.join(slots[p], owners[slots[p]], found.token); check(joined.result.ok(), "restart rejoin failed");
        const auto before = f.ingress.slots();
        check(f.ingress.publish(f.bindings[p], {f.tokens[p], 2, controls(p)}).code == IngressCode::stale_source, "restart accepted queued input");
        check(f.ingress.publish(f.bindings[p], {found.token, 2, controls(p)}).routing_status == Status::stale_binding && f.ingress.slots() == before, "restart accepted old binding");
        check(f.ingress.publish(joined.binding, {found.token, 1, controls(p)}).ok(), "fresh restart input failed");
    }
    Four other({0, 1, 2, 3}, 42);
    check(other.ingress.publish(other.bindings[0], {f.tokens[0], 1, controls(0)}).code == IngressCode::stale_source, "other session accepted token");
}
void sequence_limits() {
    Four f; f.send(0, std::numeric_limits<std::uint64_t>::max());
    const auto before = f.ingress.slots();
    for (auto seq : {std::uint64_t{0}, std::uint64_t{1}, std::numeric_limits<std::uint64_t>::max()}) {
        const auto result = f.ingress.publish(f.bindings[0], {f.tokens[0], seq, controls(0)});
        check(result.code == IngressCode::routing_rejected && result.routing_status == Status::out_of_order && f.ingress.slots() == before, "sequence wrapped or replayed");
    }
}
void device_budget() {
    Four f; auto& ingress = f.ingress;
    for (std::size_t pad = 0; pad < 4; ++pad) f.send(pad);
    std::array<DeviceToken, ControllerIngress::source_capacity> tokens{};
    for (std::size_t i = 0; i < 4; ++i) tokens[i] = f.tokens[i];
    for (std::size_t i = 4; i < tokens.size(); ++i) {
        auto found = ingress.discover(10000 + i); check(found.result.ok(), "source budget too small"); tokens[i] = found.token;
    }
    const auto before = ingress.slots();
    check(ingress.discover(999).result.code == IngressCode::capacity && ingress.active_sources() == tokens.size() && ingress.slots() == before, "budget evicted state");
    check(ingress.discover(devices[0]).token == tokens[0], "full pool rejected connected source");
    for (std::size_t pad = 0; pad < 4; ++pad) f.send(pad, 2);
    f.verify(); const auto updated = ingress.slots();
    check(ingress.remove(tokens.back()).ok(), "unassigned source removal failed");
    const auto found = ingress.discover(999); check(found.result.ok() && found.token.incarnation > tokens.back().incarnation, "budget reused generation");
    check(ingress.remove(tokens.back()).code == IngressCode::stale_source && ingress.slots() == updated, "old pool token revived or stole ownership");
}
void event_orders() {
    for (unsigned repeat = 0; repeat < 32; ++repeat) {
        std::array<std::size_t, 4> order{0, 1, 2, 3};
        do {
            Four f(order);
            for (auto pad : order) f.send(pad);
            f.verify();
            for (auto it = order.rbegin(); it != order.rend(); ++it) check(f.ingress.remove(f.tokens[*it]).ok(), "reverse removal failed");
            check(f.ingress.active_sources() == 0, "order retained source");
            for (auto pad : order) check(f.ingress.publish(f.bindings[pad], {f.tokens[pad], 2, controls(pad)}).code == IngressCode::stale_source, "order accepted late reading");
        } while (std::next_permutation(order.begin(), order.end()));
    }
}
} // namespace

int main(int argc, char** argv) {
    static_assert(!std::is_copy_constructible_v<ControllerIngress> && !std::is_move_constructible_v<ControllerIngress>);
    if (argc != 2) { std::cerr << "ERROR: exactly one case required\n"; return 2; }
    const std::string_view name = argv[1];
    try {
        if (name == "normalization") normalization();
        else if (name == "explicit-joins") explicit_joins();
        else if (name == "rejected-mutations") rejected_mutations();
        else if (name == "removal-reuse") removal_reuse();
        else if (name == "backend-restart") backend_restart();
        else if (name == "sequence-limits") sequence_limits();
        else if (name == "device-budget") device_budget();
        else if (name == "event-orders") event_orders();
        else if (name == "negative-control") {
            Four f; f.send(0);
            check(f.ingress.state(slots[0])->frame.buttons == bit(Control::east), "deliberate wrong-route rejected");
        } else { std::cerr << "ERROR: unknown case\n"; return 2; }
        std::cout << "PASS: ingress " << name << " checks=" << checks << '\n'; return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
