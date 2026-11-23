// SPDX-License-Identifier: GPL-3.0-only
// Original stimuli through the real pinned SDL library, not physical hardware.
#include "input/backend/backend.hpp"
#include <SDL3/SDL.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif
namespace in = mw3::input;
namespace b = mw3::input::backend;
namespace {
unsigned checks{}, created{}, cleaned{}, rumbles{}, zeros{}, reads{}, late{};
void check(bool value, const char* why) { ++checks; if (!value) throw std::runtime_error(why); }
constexpr std::array<std::size_t, 4> slots{2, 0, 3, 1};
constexpr std::array<in::OwnerId, 4> owners{31, 47, 61, 73};
std::string quote(std::string_view text) {
    std::string out = "\"";
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '\\' || c == '"') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + '"';
}
std::string loaded_sdl() {
#ifdef _WIN32
    const auto module = GetModuleHandleW(L"SDL3.dll"); check(module != nullptr, "SDL module missing");
    const auto symbol = reinterpret_cast<const void*>(GetProcAddress(module, "SDL_GetVersion"));
    HMODULE actual{};
    check(symbol && GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(symbol), &actual), "SDL symbol module missing");
    std::array<wchar_t, 32768> path{}; const auto n = GetModuleFileNameW(actual, path.data(), static_cast<DWORD>(path.size()));
    check(n && n < path.size(), "SDL module path truncated");
    return std::filesystem::path(path.data()).generic_string();
#else
    const auto symbol = dlsym(RTLD_DEFAULT, "SDL_GetVersion"); Dl_info info{};
    check(symbol && dladdr(symbol, &info) && info.dli_fname, "actual SDL symbol missing"); return info.dli_fname;
#endif
}
struct Pad {
    SDL_JoystickID id{}; SDL_Joystick* joystick{};
    unsigned calls{}; Uint16 low{}, high{}; std::string name;
    static bool SDLCALL Rumble(void* data, Uint16 low, Uint16 high) {
        auto& pad = *static_cast<Pad*>(data); ++pad.calls; ++rumbles;
        if (!low && !high) ++zeros;
        pad.low = low; pad.high = high; return true;
    }
    static void SDLCALL Cleanup(void*) { ++cleaned; }
    void attach(std::size_t ordinal) {
        check(!id && !joystick, "duplicate fixture attach");
        name = "MW3 original backend pad " + std::to_string(ordinal);
        SDL_VirtualJoystickDesc desc{}; SDL_INIT_INTERFACE(&desc);
        desc.type = SDL_JOYSTICK_TYPE_GAMEPAD; desc.naxes = SDL_GAMEPAD_AXIS_COUNT; desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
        desc.vendor_id = 0x1209; desc.product_id = static_cast<Uint16>(0x8900 + ordinal);
        desc.axis_mask = (1u << SDL_GAMEPAD_AXIS_COUNT) - 1; desc.button_mask = (1u << SDL_GAMEPAD_BUTTON_COUNT) - 1;
        desc.name = name.c_str(); desc.userdata = this; desc.Rumble = Rumble; desc.Cleanup = Cleanup;
        id = SDL_AttachVirtualJoystick(&desc); check(id && SDL_IsJoystickVirtual(id), "fixture attach failed"); ++created;
        joystick = SDL_OpenJoystick(id); check(joystick != nullptr, "fixture joystick open failed");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, -32768), "fixture left trigger baseline");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, -32768), "fixture right trigger baseline");
    }
    void detach() {
        if (id) { check(SDL_DetachVirtualJoystick(id), "fixture detach failed"); id = 0; }
        if (joystick) { SDL_CloseJoystick(joystick); joystick = nullptr; }
    }
    void held(std::size_t p) {
        check(SDL_SetJoystickVirtualButton(joystick, static_cast<int>(p), true), "fixture held button");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, static_cast<Sint16>((p + 1) * 4096)), "fixture held X");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTY, -32768), "fixture held up");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTX, static_cast<Sint16>(-static_cast<int>((p + 1) * 2048))), "fixture held RX");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTY, 32767), "fixture held down");
        check(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, 32767), "fixture held trigger");
    }
};
struct Lab {
    std::array<Pad, 17> pads{};
    in::ControllerIngress ingress{0x890001}; b::SdlBackend backend{ingress};
    std::array<in::DeviceToken, 4> tokens{}; std::array<in::Binding, 4> bindings{};
    bool initialized{};
    Lab() {
        for (const char* hint : {SDL_HINT_JOYSTICK_HIDAPI, SDL_HINT_JOYSTICK_RAWINPUT, SDL_HINT_JOYSTICK_DIRECTINPUT,
             SDL_HINT_JOYSTICK_WGI, SDL_HINT_XINPUT_ENABLED, SDL_HINT_JOYSTICK_IOKIT, SDL_HINT_JOYSTICK_LINUX_CLASSIC}) SDL_SetHint(hint, "0");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        check(SDL_WasInit(0) == 0 && SDL_Init(SDL_INIT_GAMEPAD), "fresh private SDL init failed"); initialized = true;
        int count = -1; auto* ids = SDL_GetJoysticks(&count); SDL_free(ids);
        check(count == 0, "unexpected external controller; refusing input");
        for (std::size_t i = 0; i < 4; ++i) check(ingress.reserve(i, owners[i]) == in::Status::ok, "owner reserve");
    }
    ~Lab() {
        (void)backend.stop();
        for (auto& pad : pads) { if (pad.id) SDL_DetachVirtualJoystick(pad.id); if (pad.joystick) SDL_CloseJoystick(pad.joystick); }
        if (initialized) SDL_Quit();
    }
    b::Result poll() { auto result = backend.poll(); reads += static_cast<unsigned>(result.published); return result; }
    void neutral() {
        check(!backend.connected() && !ingress.active_sources(), "owned backend resource remained");
        for (std::size_t i = 0; i < 4; ++i) {
            const auto state = ingress.state(i);
            check(state && state->owner == owners[i] && state->device == 0 && state->frame == in::Frame{}, "neutral owner reservation lost");
        }
    }
    void attach(const std::array<std::size_t, 4>& order = {0, 1, 2, 3}, bool held = true) {
        for (auto p : order) { pads[p].attach(p); if (held) pads[p].held(p); }
        SDL_UpdateJoysticks(); SDL_PumpEvents(); // Controls precede the first SDL_OpenGamepad.
        check(backend.start().ok() && poll().ok(), "backend start/discovery");
        check(backend.connected() == 4 && ingress.active_sources() == 4, "four discovered sources");
        for (const auto& state : ingress.slots()) check(!state.device && state.frame == in::Frame{}, "discovery assigned an owner");
        join();
    }
    void join() {
        const auto devices = backend.devices();
        for (std::size_t p = 0; p < 4; ++p) {
            const auto found = std::find_if(devices.begin(), devices.end(), [&](auto device) { return device.token.device == pads[p].id; });
            check(found != devices.end() && found->virtual_device && found->vendor == 0x1209, "actual virtual identity missing");
            tokens[p] = found->token;
            auto joined = backend.join(slots[p], owners[slots[p]], tokens[p]); check(joined.ok(), "explicit nonordinal join");
            bindings[p] = joined.route.binding;
        }
        check(poll().ok(), "joined complete read");
    }
    void verify() {
        for (std::size_t p = 0; p < 4; ++p) {
            const auto state = ingress.state(slots[p]);
            check(state && state->owner == owners[slots[p]] && state->device == pads[p].id &&
                state->frame.buttons == (std::uint64_t{1} << p), "independent button/owner route");
            const auto& f = state->frame;
            if (!(f.axes[0] > 0 && f.axes[1] == 1 && f.axes[2] < 0 && f.axes[3] == -1 && f.triggers[0] == 0 && f.triggers[1] == 1)) {
                std::cerr << "MW3_BACKEND_AXIS_FAILURE:pad=" << p << " axes=";
                for (auto value : f.axes) std::cerr << value << ',';
                std::cerr << " triggers=" << f.triggers[0] << ',' << f.triggers[1] << '\n';
            }
            check(f.axes[0] > 0 && f.axes[1] == 1 && f.axes[2] < 0 && f.axes[3] == -1 &&
                  f.triggers[0] == 0 && f.triggers[1] == 1, "complete axis/trigger route");
        }
    }
    void finish_cycle() {
        check(backend.stop().ok(), "backend stop failed"); neutral();
        check(SDL_WasInit(SDL_INIT_GAMEPAD) != 0, "backend stole caller SDL reference");
        for (const auto& pad : pads) if (pad.id) check(SDL_GetGamepadFromID(pad.id) == nullptr, "actual gamepad handle remained open");
        for (auto& pad : pads) pad.detach();
        check(created == cleaned, "virtual cleanup callbacks incomplete");
    }
    void finish() {
        finish_cycle(); SDL_Quit(); initialized = false;
        check(SDL_WasInit(0) == 0, "outer SDL lifetime leaked");
    }
};
unsigned run(Lab& lab, std::string_view name) {
    if (name == "orders") {
        std::array<std::size_t, 4> order{0, 1, 2, 3}; unsigned cycles = 0;
        do { lab.attach(order); lab.verify(); lab.finish_cycle(); ++cycles; } while (std::next_permutation(order.begin(), order.end()));
        check(cycles == 24, "not all input orders"); return cycles;
    }
    lab.attach({0, 1, 2, 3}, name != "controls");
    if (name != "controls") lab.verify();
    if (name == "held") {
        const auto before = lab.ingress.slots(); auto wrong = lab.tokens[0]; ++wrong.incarnation;
        check(!lab.backend.join(slots[0], owners[slots[0]], wrong).ok(), "late source join admitted"); ++late;
        check(!lab.backend.join(slots[0], owners[slots[1]], lab.tokens[0]).ok(), "wrong owner join admitted"); ++late;
        check(lab.ingress.slots() == before, "bad join changed another owner");
        check(lab.backend.join(slots[0], owners[slots[0]], lab.tokens[0]).ok() && lab.poll().ok(), "idempotent join reset ordering");
        lab.verify();
    } else if (name == "controls") {
        constexpr std::array<SDL_GamepadButton, 15> controls{SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST,
            SDL_GAMEPAD_BUTTON_WEST, SDL_GAMEPAD_BUTTON_NORTH, SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN,
            SDL_GAMEPAD_BUTTON_DPAD_LEFT, SDL_GAMEPAD_BUTTON_DPAD_RIGHT, SDL_GAMEPAD_BUTTON_START, SDL_GAMEPAD_BUTTON_BACK,
            SDL_GAMEPAD_BUTTON_LEFT_STICK, SDL_GAMEPAD_BUTTON_RIGHT_STICK, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER,
            SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, SDL_GAMEPAD_BUTTON_GUIDE};
        for (std::size_t i = 0; i < controls.size(); ++i) {
            check(SDL_SetJoystickVirtualButton(lab.pads[0].joystick, controls[i], true) && lab.poll().ok(), "button press failed");
            check(lab.ingress.state(slots[0])->frame.buttons == (std::uint64_t{1} << i), "named control mapping");
            check(SDL_SetJoystickVirtualButton(lab.pads[0].joystick, controls[i], false) && lab.poll().ok(), "button release failed");
            const auto begin = std::chrono::steady_clock::now();
            while (i == 14 && lab.ingress.state(slots[0])->frame.buttons &&
                   std::chrono::steady_clock::now() - begin < std::chrono::seconds(1)) {
                SDL_Delay(1); check(lab.poll().ok(), "guide release update failed");
            }
            check(lab.ingress.state(slots[0])->frame == in::Frame{}, "neutral button release");
            for (std::size_t p = 1; p < 4; ++p) check(lab.ingress.state(slots[p])->frame == in::Frame{}, "independent neutral owner changed");
        }
    } else if (name == "hotplug") {
        const auto token = lab.tokens[0]; const auto binding = lab.bindings[0];
        lab.pads[0].detach(); check(lab.poll().ok(), "disconnect poll failed");
        const auto state = lab.ingress.state(slots[0]);
        check(state->owner == owners[slots[0]] && !state->device && state->frame == in::Frame{}, "disconnect not neutral");
        check(!lab.ingress.publish(binding, {token, 99, {}}).ok(), "late input admitted"); ++late;
        lab.pads[0].attach(0); lab.pads[0].held(0); check(lab.poll().ok(), "reattach discovery failed");
        check(!lab.ingress.state(slots[0])->device, "reattach stole reserved owner");
        check(!lab.backend.join(slots[0], owners[slots[0]], token).ok(), "old source rejoined"); ++late;
        lab.join(); check(lab.tokens[0] != token, "source incarnation reused"); lab.verify();
    } else if (name == "restart") {
        const auto old = lab.tokens; const auto bindings = lab.bindings;
        check(lab.backend.stop().ok(), "restart stop"); lab.neutral();
        check(lab.backend.start().ok() && lab.poll().ok(), "restart start");
        for (std::size_t p = 0; p < 4; ++p) {
            check(!lab.backend.join(slots[p], owners[slots[p]], old[p]).ok(), "old restart source rejoined"); ++late;
            check(lab.backend.rumble(bindings[p], old[p], 1, 2, 30) == b::Code::stale_binding, "old restart motor admitted"); ++late;
        }
        lab.join();
        for (std::size_t p = 0; p < 4; ++p) check(lab.tokens[p].device == old[p].device && lab.tokens[p].incarnation != old[p].incarnation, "raw ID reuse not guarded");
        lab.verify(); return 2;
    } else if (name == "rumble") {
        auto wrong = lab.bindings[0]; ++wrong.owner; const unsigned before = rumbles;
        check(lab.backend.rumble(wrong, lab.tokens[0], 123, 456, 200) == b::Code::stale_binding, "wrong owner motor admitted"); ++late;
        check(lab.backend.rumble(lab.bindings[0], lab.tokens[1], 123, 456, 200) == b::Code::stale_binding, "wrong source motor admitted"); ++late;
        check(rumbles == before, "rejected motor reached SDL");
        check(lab.backend.rumble(lab.bindings[0], lab.tokens[0], 1, 2, 5001) == b::Code::invalid_rumble, "unbounded motor duration");
        check(lab.backend.rumble(lab.bindings[0], lab.tokens[0], 1, 2, 0) == b::Code::invalid_rumble, "zero duration motor admitted");
        for (std::size_t p = 0; p < 4; ++p) {
            check(lab.backend.rumble(lab.bindings[p], lab.tokens[p], static_cast<Uint16>(1000 + p), static_cast<Uint16>(2000 + p), 5000) == b::Code::ok, "actual virtual rumble failed");
            check(lab.pads[p].low == 1000 + p && lab.pads[p].high == 2000 + p, "motor routed to wrong source");
        }
        check(lab.backend.stop().ok(), "motor cleanup stop failed");
        for (std::size_t p = 0; p < 4; ++p) check(lab.pads[p].low == 0 && lab.pads[p].high == 0, "motor not stopped");
        lab.neutral();
    } else if (name == "budget") {
        for (std::size_t p = 4; p < 17; ++p) lab.pads[p].attach(p);
        const auto result = lab.poll();
        check(result.code == b::Code::capacity && result.connected == 16 && result.published == 4 && lab.ingress.active_sources() == 16, "bounded source budget");
        lab.verify();
    } else if (name == "lifetime") {
        const auto before = lab.ingress.slots(); b::Code foreign{};
        std::thread worker([&] { foreign = lab.backend.poll().code; }); worker.join();
        check(foreign == b::Code::wrong_thread && before == lab.ingress.slots(), "foreign thread changed input");
        const auto custom = SDL_RegisterEvents(1); check(custom != 0, "custom event unavailable");
        SDL_Event event{}; event.type = custom; event.user.code = 0x89;
        check(SDL_PushEvent(&event) && lab.poll().ok(), "custom event setup");
        SDL_Event held{}; check(SDL_PeepEvents(&held, 1, SDL_GETEVENT, custom, custom) == 1 && held.user.code == 0x89, "backend consumed caller event");
        check(lab.backend.start().code == b::Code::already_running, "second start acquired another reference");
        in::ControllerIngress other{0x890099}; check(other.discover(123).result.ok(), "external source fixture");
        b::SdlBackend conflict{other};
        check(conflict.start().code == b::Code::source_conflict && other.active_sources() == 1, "another source domain was changed");
        lab.verify();
    } else throw std::runtime_error("unknown case");
    return 1;
}
} // namespace
int main(int argc, char** argv) {
    if (argc < 3 || argc > 4) { std::cerr << "MW3_BACKEND_FAILURE:arguments\n"; return 2; }
    const std::string name = argv[1], nonce = argv[2], control = argc == 4 ? argv[3] : "";
    const std::array<std::string_view, 8> cases{"held", "controls", "orders", "hotplug", "restart", "rumble", "budget", "lifetime"};
    if (std::find(cases.begin(), cases.end(), name) == cases.end() || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= 'a' && c <= 'f') || (c >= '0' && c <= '9'); }) ||
        (!control.empty() && (name != "held" || (control != "--wrong-route" && control != "--incomplete" && control != "--deadline")))) {
        std::cerr << "MW3_BACKEND_FAILURE:case/nonce/control\n"; return 2;
    }
    try {
        const auto path = loaded_sdl(); check(SDL_GetVersion() == b::sdl_version, "SDL version differs");
        std::cout << "MW3_BACKEND_LOADED:{\"nonce\":" << quote(nonce) << ",\"sdl\":" << quote(path) << ",\"version\":" << SDL_GetVersion() << "}\n" << std::flush;
        Lab lab; const auto cycles = run(lab, name);
        const bool wrong_route_rejected = lab.ingress.state(slots[0])->frame.buttons != (std::uint64_t{1} << 1);
        lab.finish();
        std::cout << "MW3_BACKEND_READY:" << nonce << '\n' << std::flush;
        if (control == "--incomplete") return 0;
        const bool rejected = control == "--wrong-route" && wrong_route_rejected;
        std::cout << (rejected ? "MW3_BACKEND_REJECTED:" : "MW3_BACKEND_COMPLETE:")
            << "{\"schema\":1,\"case\":" << quote(name) << ",\"nonce\":" << quote(nonce) << ",\"sdl\":" << quote(path)
            << ",\"version\":" << SDL_GetVersion() << ",\"cycles\":" << cycles << ",\"created\":" << created << ",\"cleaned\":" << cleaned
            << ",\"owners\":4,\"sources_after\":0,\"handles_after\":0,\"sdl_after\":" << SDL_WasInit(0)
            << ",\"reads\":" << reads << ",\"rumble_calls\":" << rumbles << ",\"rumble_zeros\":" << zeros
            << ",\"late_rejections\":" << late << ",\"checks\":" << checks << "}\n" << std::flush;
        if (control == "--wrong-route") {
            check(wrong_route_rejected, "wrong-route control did not discriminate");
            std::cerr << "MW3_BACKEND_FAILURE:deliberate wrong-route rejected\n"; return 1;
        }
        if (control == "--deadline") SDL_Delay(30000);
        return 0;
    } catch (const std::exception& error) { std::cerr << "MW3_BACKEND_FAILURE:" << error.what() << '\n'; return 1; }
}
