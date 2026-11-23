// SPDX-License-Identifier: GPL-3.0-only
// Adapted SDL device handling/control reads from PaulCombal/mw2-recompiled.
// The explicit owner/incarnation/lifetime layer is original; see NOTICE.md.
#include "backend.hpp"
#include <SDL3/SDL.h>
#include <algorithm>
#include <exception>
#include <limits>

namespace mw3::input::backend {
static_assert(SDL_VERSION == sdl_version, "Use the pinned SDL headers");
namespace {
// Named SDL controls, deliberately mapped to our host bits, never Xbox bits.
constexpr std::array<SDL_GamepadButton, 15> buttons{
    SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST, SDL_GAMEPAD_BUTTON_WEST,
    SDL_GAMEPAD_BUTTON_NORTH, SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN,
    SDL_GAMEPAD_BUTTON_DPAD_LEFT, SDL_GAMEPAD_BUTTON_DPAD_RIGHT, SDL_GAMEPAD_BUTTON_START,
    SDL_GAMEPAD_BUTTON_BACK, SDL_GAMEPAD_BUTTON_LEFT_STICK, SDL_GAMEPAD_BUTTON_RIGHT_STICK,
    SDL_GAMEPAD_BUTTON_LEFT_SHOULDER, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, SDL_GAMEPAD_BUTTON_GUIDE};
constexpr std::array<SDL_GamepadAxis, 6> axes{
    SDL_GAMEPAD_AXIS_LEFTX, SDL_GAMEPAD_AXIS_LEFTY, SDL_GAMEPAD_AXIS_RIGHTX,
    SDL_GAMEPAD_AXIS_RIGHTY, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER};
void remember(Code& first, Code next) { if (first == Code::ok && next != Code::ok) first = next; }
} // namespace

SdlBackend::~SdlBackend() {
    // SDL teardown on another thread violates this object's explicit contract.
    if (running_ && !on_thread()) std::terminate();
    (void)stop();
}
Code SdlBackend::ready() const noexcept {
    if (!on_thread()) return Code::wrong_thread;
    if (!running_) return Code::not_running;
    if (!SDL_IsMainThread()) return Code::wrong_thread;
    return Code::ok;
}
std::size_t SdlBackend::connected() const noexcept {
    return std::count_if(entries_.begin(), entries_.end(), [](const auto& entry) { return entry.pad != nullptr; });
}
std::array<Device, SdlBackend::capacity> SdlBackend::devices() const noexcept {
    std::array<Device, capacity> result{};
    for (std::size_t i = 0; i < capacity; ++i) result[i] = entries_[i].info;
    return result;
}
Result SdlBackend::start() noexcept {
    if (!on_thread() || !SDL_IsMainThread()) return {Code::wrong_thread};
    if (running_) return {Code::already_running, connected()};
    if (ingress_.active_sources()) return {Code::source_conflict};
    if (SDL_GetVersion() != sdl_version) return {Code::version_mismatch};
    if (!SDL_InitSubSystem(SDL_INIT_GAMEPAD)) return {Code::sdl_error};
    running_ = true;
    return {Code::ok};
}
Code SdlBackend::drop(Entry& entry) noexcept {
    if (!entry.pad) return Code::ok;
    Code result = Code::ok;
    if (entry.rumbling && SDL_GamepadConnected(entry.pad) && !SDL_RumbleGamepad(entry.pad, 0, 0, 0)) result = Code::sdl_error;
    SDL_CloseGamepad(entry.pad);
    if (!ingress_.remove(entry.info.token).ok()) remember(result, Code::ingress_rejected);
    entry = {};
    return result;
}
Result SdlBackend::stop() noexcept {
    if (!on_thread()) return {Code::wrong_thread};
    if (!running_) return {Code::ok};
    if (!SDL_IsMainThread()) return {Code::wrong_thread, connected()};
    Code result = Code::ok;
    for (auto& entry : entries_) remember(result, drop(entry));
    SDL_QuitSubSystem(SDL_INIT_GAMEPAD);
    running_ = false;
    return {result};
}
bool SdlBackend::current(const Entry& entry, const Binding& binding) const noexcept {
    if (!entry.binding || *entry.binding != binding) return false;
    const auto state = ingress_.state(binding.slot);
    return state && state->owner == binding.owner && state->device == binding.device &&
           state->generation == binding.generation;
}
Joined SdlBackend::join(std::size_t slot, OwnerId owner, const DeviceToken& token) noexcept {
    const auto code = ready();
    if (code != Code::ok) return {code};
    for (auto& entry : entries_) if (entry.pad && entry.info.token == token) {
        const auto joined = ingress_.join(slot, owner, token);
        if (!joined.result.ok()) return {Code::ingress_rejected, joined};
        if (!entry.binding || *entry.binding != joined.binding) entry.sequence = 0;
        entry.binding = joined.binding;
        return {Code::ok, joined};
    }
    return {Code::stale_binding};
}
Code SdlBackend::rumble(const Binding& binding, const DeviceToken& token,
                        std::uint16_t low, std::uint16_t high, std::uint32_t milliseconds) noexcept {
    const auto code = ready();
    if (code != Code::ok) return code;
    for (auto& entry : entries_) if (entry.pad && entry.info.token == token) {
        if (!current(entry, binding)) return Code::stale_binding;
        if (milliseconds > maximum_rumble_ms || ((low || high) && milliseconds == 0)) return Code::invalid_rumble;
        if (!SDL_GamepadConnected(entry.pad)) return Code::stale_binding;
        if (!SDL_RumbleGamepad(entry.pad, low, high, milliseconds)) return Code::sdl_error;
        entry.rumbling = low || high;
        return Code::ok;
    }
    return Code::stale_binding;
}
Result SdlBackend::poll() noexcept {
    const auto code = ready();
    if (code != Code::ok) return {code};
    SDL_PumpEvents(); // Update, never consume another caller's queued events.
    SDL_UpdateGamepads();
    Code result = Code::ok;
    int count = 0;
    SDL_JoystickID* ids = SDL_GetGamepads(&count);
    if (!ids || count < 0) {
        for (auto& entry : entries_) (void)drop(entry);
        SDL_free(ids);
        return {Code::sdl_error};
    }
    for (auto& entry : entries_) if (entry.pad && !SDL_GamepadConnected(entry.pad)) remember(result, drop(entry));
    if (count > static_cast<int>(capacity)) remember(result, Code::capacity);
    for (int i = 0; i < std::min(count, static_cast<int>(capacity)); ++i) {
        if (std::any_of(entries_.begin(), entries_.end(), [&](const auto& entry) { return entry.pad && entry.info.token.device == ids[i]; })) continue;
        auto free = std::find_if(entries_.begin(), entries_.end(), [](const auto& entry) { return !entry.pad; });
        if (free == entries_.end()) { remember(result, Code::capacity); break; }
        auto* pad = SDL_OpenGamepad(ids[i]);
        if (!pad) { remember(result, Code::sdl_error); continue; }
        const auto discovery = ingress_.discover(ids[i]);
        if (!discovery.result.ok()) { SDL_CloseGamepad(pad); remember(result, Code::ingress_rejected); continue; }
        *free = Entry{pad, {discovery.token, SDL_GetGamepadVendor(pad), SDL_GetGamepadProduct(pad), SDL_IsJoystickVirtual(ids[i])}};
    }
    SDL_free(ids);
    SDL_UpdateGamepads(); // Includes held controls before the first open.
    std::size_t published = 0;
    for (auto& entry : entries_) if (entry.pad && entry.binding) {
        if (entry.sequence == std::numeric_limits<std::uint64_t>::max()) {
            (void)drop(entry); remember(result, Code::sequence_exhausted); continue;
        }
        std::uint32_t mask = 0;
        std::array<std::int16_t, 6> values{};
        SDL_LockJoysticks();
        for (std::size_t i = 0; i < buttons.size(); ++i) if (SDL_GetGamepadButton(entry.pad, buttons[i])) mask |= std::uint32_t{1} << i;
        for (std::size_t i = 0; i < axes.size(); ++i) values[i] = SDL_GetGamepadAxis(entry.pad, axes[i]);
        const bool attached = SDL_GamepadConnected(entry.pad);
        SDL_UnlockJoysticks();
        const auto controls = convert(mask, values);
        if (!attached || !controls) {
            (void)drop(entry); remember(result, attached ? Code::invalid_controls : Code::stale_binding); continue;
        }
        if (!ingress_.publish(*entry.binding, {entry.info.token, entry.sequence + 1, *controls}).ok()) {
            (void)drop(entry); remember(result, Code::ingress_rejected); continue;
        }
        ++entry.sequence; ++published;
    }
    return {result, connected(), published};
}
} // namespace mw3::input::backend
