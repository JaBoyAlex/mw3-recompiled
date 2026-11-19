// SPDX-License-Identifier: GPL-3.0-only
#include "input/slot_router.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>

using namespace mw3::input;
namespace {
void check(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}
template<class Action>
void rejects(SlotRouter& router, Status expected, Action action) {
    const auto before = router.slots();
    check(action() == expected, "unexpected rejection status");
    check(router.slots() == before, "rejected event changed a slot");
}
Frame pattern(std::size_t i) {
    return {std::uint64_t{1} << i,
            {static_cast<float>(i) / 4.0f, -1.0f, 1.0f, 0.0f},
            {static_cast<float>(i) / 4.0f, 1.0f}};
}
Binding connect(SlotRouter& router, std::size_t slot, OwnerId owner, DeviceId device) {
    check(router.reserve(slot, owner) == Status::ok, "reserve failed");
    const auto result = router.attach(slot, owner, device);
    check(result.status == Status::ok, "attach failed");
    return result.binding;
}

void four_slots() {
    static_assert(!std::is_copy_constructible_v<SlotRouter> && !std::is_move_constructible_v<SlotRouter>);
    SlotRouter router(100);
    check(router.slots() == std::array<SlotState, 4>{}, "initial state not neutral");
    std::array<Binding, 4> tokens{};
    for (std::size_t i = 0; i < 4; ++i) tokens[i] = connect(router, i, 10 + i, 20 + i);
    for (std::size_t i = 0; i < 4; ++i) {
        const auto before = router.slots();
        check(router.apply(tokens[i], 1, pattern(i)) == Status::ok, "frame rejected");
        for (std::size_t j = 0; j < 4; ++j) {
            if (i != j) check(router.slots()[j] == before[j], "cross-slot frame write");
        }
    }
    for (std::size_t i = 0; i < 4; ++i) {
        const auto state = router.state(i);
        check(state && state->owner == 10 + i && state->device == 20 + i &&
              state->last_sequence == 1 && state->frame == pattern(i), "four independent inputs lost");
        const auto before = router.slots();
        check(router.reserve(i, 10 + i) == Status::ok, "idempotent reservation failed");
        const auto again = router.attach(i, 10 + i, 20 + i);
        check(again.status == Status::ok && again.binding == tokens[i] &&
              router.slots() == before, "idempotent attach reset input or token");
    }
    check(!router.state(4) && !router.state(std::numeric_limits<std::size_t>::max()), "invalid query accepted");
}

void assignment_guards() {
    SlotRouter router(101);
    const auto first = connect(router, 0, 10, 20);
    check(router.apply(first, 1, pattern(0)) == Status::ok, "initial frame failed");
    rejects(router, Status::duplicate_owner, [&] { return router.reserve(1, 10); });
    rejects(router, Status::slot_occupied, [&] { return router.reserve(0, 11); });
    rejects(router, Status::wrong_owner, [&] { return router.attach(0, 11, 21).status; });
    rejects(router, Status::slot_occupied, [&] { return router.attach(0, 10, 21).status; });
    rejects(router, Status::wrong_owner, [&] { return router.attach(1, 11, 21).status; });
    check(router.reserve(1, 11) == Status::ok, "second reserve failed");
    rejects(router, Status::duplicate_device, [&] { return router.attach(1, 11, 20).status; });
    rejects(router, Status::wrong_owner, [&] { return router.release(0, 11); });
    rejects(router, Status::invalid_identity, [&] { return router.reserve(2, 0); });
    rejects(router, Status::invalid_identity, [&] { return router.attach(0, 0, 20).status; });
    rejects(router, Status::invalid_identity, [&] { return router.attach(0, 10, 0).status; });
    rejects(router, Status::invalid_identity, [&] { return router.release(0, 0); });
    for (auto slot : {std::size_t{4}, std::numeric_limits<std::size_t>::max()}) {
        rejects(router, Status::invalid_slot, [&] { return router.reserve(slot, 12); });
        rejects(router, Status::invalid_slot, [&] { return router.attach(slot, 12, 22).status; });
        rejects(router, Status::invalid_slot, [&] { return router.release(slot, 12); });
    }
    check(router.attach(0, 10, 21).binding == Binding{}, "failed attach leaked a binding");
}

void disconnect_reconnect() {
    SlotRouter router(102);
    const auto original = connect(router, 2, 12, 22);
    const auto other = connect(router, 0, 10, 20);
    check(router.apply(other, 1, pattern(0)) == Status::ok &&
          router.apply(original, 88, pattern(2)) == Status::ok, "initial input failed");
    const auto before = router.slots();
    check(router.disconnect(original) == Status::ok, "disconnect failed");
    check(router.slots()[2].owner == 12 && router.slots()[2].device == 0 &&
          router.slots()[2].frame == Frame{} && router.slots()[2].last_sequence == 0,
          "disconnect lost reservation or left held input");
    for (std::size_t i = 0; i < 4; ++i) {
        if (i != 2) check(router.slots()[i] == before[i], "disconnect changed another slot");
    }
    rejects(router, Status::stale_binding, [&] { return router.apply(original, 89, pattern(2)); });
    rejects(router, Status::stale_binding, [&] { return router.disconnect(original); });
    rejects(router, Status::slot_occupied, [&] { return router.reserve(2, 13); });
    rejects(router, Status::duplicate_owner, [&] { return router.reserve(3, 12); });
    const auto replacement = router.attach(2, 12, 23);
    check(replacement.status == Status::ok && replacement.binding != original, "reconnect reused token");
    check(router.apply(replacement.binding, 1, pattern(3)) == Status::ok, "new binding sequence not reset");
    rejects(router, Status::stale_binding, [&] { return router.disconnect(original); });
    check(router.release(2, 12) == Status::ok, "explicit release failed");
    check(router.slots()[2].owner == 0 && router.slots()[2].device == 0 &&
          router.slots()[2].frame == Frame{}, "release not neutral");
    const auto restored = connect(router, 2, 12, 22);
    check(restored != original, "release revived original owner/device token");
    rejects(router, Status::stale_binding, [&] { return router.apply(original, 99, pattern(2)); });
    rejects(router, Status::stale_binding, [&] { return router.apply(replacement.binding, 2, pattern(3)); });
    check(router.release(2, 12) == Status::ok, "second release failed");
    const auto reassigned = connect(router, 2, 13, 22);
    check(router.apply(reassigned, 1, pattern(1)) == Status::ok, "explicit new owner failed");
    rejects(router, Status::wrong_owner, [&] { return router.release(2, 12); });
}

void stale_sessions() {
    SlotRouter first(103), second(104), disabled(0);
    const auto token = connect(first, 0, 10, 20);
    const auto other = connect(second, 0, 10, 20);
    check(token.generation == other.generation, "session control must share local generation");
    rejects(second, Status::stale_binding, [&] { return second.apply(token, 1, pattern(0)); });
    rejects(second, Status::stale_binding, [&] { return second.disconnect(token); });
    for (int field = 0; field < 5; ++field) {
        auto changed = token;
        if (field == 0) changed.session = 0;
        if (field == 1) changed.generation = 0;
        if (field == 2) changed.owner = 99;
        if (field == 3) changed.device = 99;
        if (field == 4) changed.slot = 1;
        rejects(first, Status::stale_binding, [&] { return first.apply(changed, 1, pattern(0)); });
        rejects(first, Status::stale_binding, [&] { return first.disconnect(changed); });
    }
    auto invalid = token;
    invalid.slot = std::numeric_limits<std::size_t>::max();
    rejects(first, Status::invalid_slot, [&] { return first.apply(invalid, 1, pattern(0)); });
    rejects(first, Status::invalid_slot, [&] { return first.disconnect(invalid); });
    rejects(disabled, Status::invalid_session, [&] { return disabled.reserve(0, 10); });
    rejects(disabled, Status::invalid_session, [&] { return disabled.attach(0, 10, 20).status; });
    rejects(disabled, Status::invalid_session, [&] { return disabled.apply(token, 1, pattern(0)); });
    rejects(disabled, Status::invalid_session, [&] { return disabled.disconnect(token); });
    rejects(disabled, Status::invalid_session, [&] { return disabled.release(0, 10); });
}

void frame_validation() {
    SlotRouter router(105);
    const auto token = connect(router, 0, 10, 20);
    check(router.apply(token, 1, pattern(0)) == Status::ok, "initial frame failed");
    const std::array invalid{std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(), -1.25f, 1.25f};
    for (std::size_t component = 0; component < 6; ++component) {
        for (float value : invalid) {
            auto frame = pattern(3);
            if (component < 4) frame.axes[component] = value;
            else frame.triggers[component - 4] = value;
            rejects(router, Status::invalid_frame, [&] { return router.apply(token, 2, frame); });
        }
    }
    for (std::size_t trigger = 0; trigger < 2; ++trigger) {
        auto frame = pattern(3);
        frame.triggers[trigger] = -0.001f;
        rejects(router, Status::invalid_frame, [&] { return router.apply(token, 2, frame); });
    }
    Frame edges{std::numeric_limits<std::uint64_t>::max(), {-1, 1, -0.0f, 0}, {0, 1}};
    check(router.apply(token, 2, edges) == Status::ok && router.slots()[0].frame == edges,
          "valid edges rejected or invalid sample consumed sequence");
    check(router.apply(token, 3, Frame{}) == Status::ok && router.slots()[0].frame == Frame{},
          "whole neutral frame failed");
}

void sequence_limits() {
    SlotRouter router(106);
    const auto token = connect(router, 0, 10, 20);
    rejects(router, Status::out_of_order, [&] { return router.apply(token, 0, pattern(0)); });
    check(router.apply(token, 9, pattern(0)) == Status::ok, "sequence gap rejected");
    for (auto value : {std::uint64_t{0}, std::uint64_t{8}, std::uint64_t{9}}) {
        rejects(router, Status::out_of_order, [&] { return router.apply(token, value, pattern(1)); });
    }
    const auto maximum = std::numeric_limits<std::uint64_t>::max();
    check(router.apply(token, maximum, pattern(2)) == Status::ok, "maximum sequence rejected");
    for (auto value : {std::uint64_t{0}, std::uint64_t{1}, maximum}) {
        rejects(router, Status::out_of_order, [&] { return router.apply(token, value, pattern(3)); });
    }
    check(router.disconnect(token) == Status::ok, "sequence exhaustion disconnect failed");
    const auto next = router.attach(0, 10, 20);
    check(next.status == Status::ok && next.binding.generation > token.generation &&
          router.apply(next.binding, 1, pattern(1)) == Status::ok, "reconnect sequence restart failed");
    rejects(router, Status::stale_binding, [&] { return router.apply(token, maximum, pattern(2)); });
}

void event_orders() {
    std::array<std::size_t, 4> order{0, 1, 2, 3};
    std::uint64_t session = 200;
    std::size_t scenarios = 0;
    do {
        for (unsigned repeat = 0; repeat < 32; ++repeat) {
            SlotRouter router(session++);
            std::array<Binding, 4> tokens{};
            for (auto i : order) tokens[i] = connect(router, i, 10 + i, 20 + i);
            for (auto i : order) check(router.apply(tokens[i], 10, pattern(i)) == Status::ok, "permuted sample failed");
            for (auto it = order.rbegin(); it != order.rend(); ++it) {
                const auto i = *it;
                const auto before = router.slots();
                check(router.disconnect(tokens[i]) == Status::ok, "permuted disconnect failed");
                for (std::size_t j = 0; j < 4; ++j) {
                    if (i != j) check(router.slots()[j] == before[j], "permuted cross-slot write");
                }
                rejects(router, Status::stale_binding, [&] { return router.apply(tokens[i], 11, pattern(i)); });
                const auto next = router.attach(i, 10 + i, 20 + i);
                check(next.status == Status::ok && router.apply(next.binding, 1, pattern(i)) == Status::ok,
                      "permuted reconnect failed");
                rejects(router, Status::stale_binding, [&] { return router.disconnect(tokens[i]); });
            }
            for (auto i : order) {
                check(router.slots()[i].frame == pattern(i), "permuted input pattern changed");
                check(router.release(i, 10 + i) == Status::ok, "permuted release failed");
                check(router.slots()[i].frame == Frame{} && router.slots()[i].owner == 0,
                      "permuted release left input");
            }
            ++scenarios;
        }
    } while (std::next_permutation(order.begin(), order.end()));
    check(scenarios == 768, "event order coverage incomplete");
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "ERROR: exactly one case required\n"; return 2; }
    const std::string_view name(argv[1]);
    try {
        if (name == "four-slots") four_slots();
        else if (name == "assignment-guards") assignment_guards();
        else if (name == "disconnect-reconnect") disconnect_reconnect();
        else if (name == "stale-sessions") stale_sessions();
        else if (name == "frame-validation") frame_validation();
        else if (name == "sequence-limits") sequence_limits();
        else if (name == "event-orders") event_orders();
        else if (name == "negative-control") {
            SlotRouter router(999);
            const auto token = connect(router, 0, 10, 20);
            check(router.apply(token, 1, pattern(0)) == Status::ok, "control setup failed");
            auto wrong = pattern(0);
            wrong.buttons = 8;
            check(router.slots()[0].frame == wrong, "deliberate wrong-result rejected");
        } else { std::cerr << "ERROR: unknown case\n"; return 2; }
        std::cout << "PASS: " << name << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
