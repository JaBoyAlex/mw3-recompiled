// SPDX-License-Identifier: GPL-3.0-only
// SDL input portions adapted from PaulCombal/mw2-recompiled; see NOTICE.md.
#pragma once
#include "input/ingress/ingress.hpp"
#include <thread>

struct SDL_Gamepad;

namespace mw3::input::backend {
inline constexpr int sdl_version = 3004014;

// SDL Y points down; ingress Y points up. Preserve full endpoints and exact
// neutral. As with the upstream complement, -1 and 0 both map to zero here.
constexpr std::int16_t invert_y(std::int16_t value) noexcept {
    return value == 0 ? 0 : static_cast<std::int16_t>(-1 - static_cast<std::int32_t>(value));
}
inline std::optional<RawControls> convert(std::uint32_t buttons,
                                        const std::array<std::int16_t, 6>& axes) noexcept {
    if ((buttons & ~known_controls) || axes[4] < 0 || axes[5] < 0) return std::nullopt;
    return RawControls{buttons, {axes[0], invert_y(axes[1]), axes[2], invert_y(axes[3])},
                       {static_cast<std::uint8_t>(axes[4] >> 7), static_cast<std::uint8_t>(axes[5] >> 7)}};
}

enum class Code {
    ok, not_running, already_running, wrong_thread, version_mismatch,
    sdl_error, capacity, ingress_rejected, stale_binding, invalid_rumble,
    invalid_controls, sequence_exhausted, source_conflict,
};
struct Result {
    Code code{Code::not_running};
    std::size_t connected{}, published{};
    [[nodiscard]] bool ok() const noexcept { return code == Code::ok; }
};
struct Joined {
    Code code{Code::not_running};
    Join route{};
    [[nodiscard]] bool ok() const noexcept { return code == Code::ok && route.result.ok(); }
};
struct Device {
    DeviceToken token{};
    std::uint16_t vendor{}, product{};
    bool virtual_device{};
};

// One creator/main thread owns calls and destruction. The caller owns the SDL
// process lifetime (Init(0)/Quit), owner reservations and the ingress lifetime.
// This adapter balances only its own GAMEPAD reference and handles. Route SDL
// sources via join(); do not publish them or attach them through another path.
class SdlBackend final {
public:
    static constexpr std::size_t capacity = ControllerIngress::source_capacity;
    static constexpr std::uint32_t maximum_rumble_ms = 5000;
    explicit SdlBackend(ControllerIngress& ingress) noexcept : ingress_(ingress) {}
    ~SdlBackend();
    SdlBackend(const SdlBackend&) = delete;
    SdlBackend& operator=(const SdlBackend&) = delete;
    SdlBackend(SdlBackend&&) = delete;
    SdlBackend& operator=(SdlBackend&&) = delete;
    [[nodiscard]] Result start() noexcept;
    [[nodiscard]] Result poll() noexcept;
    [[nodiscard]] Result stop() noexcept;
    [[nodiscard]] Joined join(std::size_t slot, OwnerId owner, const DeviceToken& token) noexcept;
    [[nodiscard]] Code rumble(const Binding& binding, const DeviceToken& token,
                              std::uint16_t low, std::uint16_t high, std::uint32_t milliseconds) noexcept;
    [[nodiscard]] std::array<Device, capacity> devices() const noexcept;
    [[nodiscard]] std::size_t connected() const noexcept;

private:
    struct Entry {
        SDL_Gamepad* pad{};
        Device info{};
        std::optional<Binding> binding{};
        std::uint64_t sequence{};
        bool rumbling{};
    };
    [[nodiscard]] bool on_thread() const noexcept { return std::this_thread::get_id() == thread_; }
    [[nodiscard]] Code ready() const noexcept;
    [[nodiscard]] Code drop(Entry& entry) noexcept;
    [[nodiscard]] bool current(const Entry& entry, const Binding& binding) const noexcept;
    ControllerIngress& ingress_;
    const std::thread::id thread_{std::this_thread::get_id()};
    std::array<Entry, capacity> entries_{};
    bool running_{};
};
} // namespace mw3::input::backend
