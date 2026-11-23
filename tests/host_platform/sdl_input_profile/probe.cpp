// SPDX-License-Identifier: GPL-3.0-only
// Original public-API stimuli; no SDL implementation or guest code compiled here.
#include <SDL3/SDL.h>
#include <algorithm>
#include <array>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif
namespace {
unsigned checks{}, created{}, cleaned{};
void check(bool value, const char* why) { ++checks; if (!value) throw std::runtime_error(why); }
std::string quote(std::string_view text) {
    std::string out = "\""; constexpr char hex[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '\\' || c == '"') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + '"';
}
std::string module() {
#ifdef _WIN32
    const auto handle = GetModuleHandleW(L"SDL3.dll"); check(handle != nullptr, "SDL library missing");
    const auto symbol = reinterpret_cast<const void*>(GetProcAddress(handle, "SDL_GetVersion")); HMODULE actual{};
    check(symbol && GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(symbol), &actual), "SDL actual export module missing");
    std::array<wchar_t, 32768> path{}; const auto n = GetModuleFileNameW(actual, path.data(), static_cast<DWORD>(path.size()));
    check(n && n < path.size(), "SDL export path truncated"); return std::filesystem::path(path.data()).generic_string();
#else
    Dl_info info{}; const auto symbol = dlsym(RTLD_DEFAULT, "SDL_GetVersion");
    check(symbol && dladdr(symbol, &info) && info.dli_fname, "actual SDL export unavailable"); return info.dli_fname;
#endif
}
using Pair = std::array<Sint16, 2>;
constexpr std::array<Pair, 2> held{{{32767, 16384}, {-32768, 32767}}};
std::string numbers(Pair p) { return '[' + std::to_string(p[0]) + ',' + std::to_string(p[1]) + ']'; }
struct Pad {
    SDL_JoystickID id{}; SDL_Joystick* raw{}; SDL_Gamepad* first{}; SDL_Gamepad* second{}; std::string name;
    static void SDLCALL Cleanup(void*) { ++cleaned; }
    void attach(unsigned p) {
        SDL_VirtualJoystickDesc desc{}; SDL_INIT_INTERFACE(&desc);
        desc.type = SDL_JOYSTICK_TYPE_GAMEPAD; desc.vendor_id = 0xffff; desc.product_id = static_cast<Uint16>(0x9000 + p);
        desc.naxes = SDL_GAMEPAD_AXIS_COUNT; desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
        desc.axis_mask = (1u << SDL_GAMEPAD_AXIS_COUNT) - 1; desc.button_mask = (1u << SDL_GAMEPAD_BUTTON_COUNT) - 1;
        name = "MW3 original SDL trigger " + std::to_string(p); desc.name = name.c_str(); desc.userdata = this; desc.Cleanup = Cleanup;
        id = SDL_AttachVirtualJoystick(&desc); check(id && SDL_IsJoystickVirtual(id), "owned virtual attach"); ++created;
        raw = SDL_OpenJoystick(id); check(raw != nullptr, "owned raw open");
        set({-32768, -32768}); SDL_UpdateJoysticks();
        check(SDL_SetJoystickVirtualAxis(raw, SDL_GAMEPAD_AXIS_LEFTX, static_cast<Sint16>(1024 * (p + 1))), "owned stick stimulus");
        check(SDL_SetJoystickVirtualButton(raw, static_cast<int>(p), true), "owned button stimulus");
    }
    void set(Pair values) {
        check(SDL_SetJoystickVirtualAxis(raw, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, values[0]), "left trigger stimulus");
        check(SDL_SetJoystickVirtualAxis(raw, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, values[1]), "right trigger stimulus");
    }
    Pair sample() { return {SDL_GetJoystickAxis(raw, SDL_GAMEPAD_AXIS_LEFT_TRIGGER), SDL_GetJoystickAxis(raw, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)}; }
    Pair mapped() { return {SDL_GetGamepadAxis(first, SDL_GAMEPAD_AXIS_LEFT_TRIGGER), SDL_GetGamepadAxis(first, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)}; }
    void open() { first = SDL_OpenGamepad(id); check(first != nullptr, "owned gamepad open"); }
    void close() { if (second) { SDL_CloseGamepad(second); second = nullptr; } if (first) { SDL_CloseGamepad(first); first = nullptr; } }
    void cleanup() {
        close();
        if (id) { check(SDL_GetGamepadFromID(id) == nullptr, "owned actual gamepad handle remained"); check(SDL_DetachVirtualJoystick(id), "owned virtual detach"); id = 0; }
        if (raw) { SDL_CloseJoystick(raw); raw = nullptr; }
    }
};
struct Fixture {
    std::array<Pad, 2> pads{}; bool initialized{};
    Fixture() {
        for (const char* hint : {SDL_HINT_JOYSTICK_HIDAPI, SDL_HINT_JOYSTICK_RAWINPUT, SDL_HINT_JOYSTICK_DIRECTINPUT,
             SDL_HINT_JOYSTICK_WGI, SDL_HINT_XINPUT_ENABLED, SDL_HINT_JOYSTICK_IOKIT, SDL_HINT_JOYSTICK_LINUX_CLASSIC}) SDL_SetHint(hint, "0");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        check(SDL_WasInit(0) == 0 && SDL_Init(SDL_INIT_GAMEPAD), "private SDL initialization"); initialized = true;
        int count = -1; auto* ids = SDL_GetJoysticks(&count); SDL_free(ids); check(count == 0, "external device present; refusing input");
        for (unsigned p = 0; p < 2; ++p) pads[p].attach(p);
    }
    ~Fixture() {
        for (auto& p : pads) { p.close(); if (p.id) SDL_DetachVirtualJoystick(p.id); if (p.raw) SDL_CloseJoystick(p.raw); }
        if (initialized) SDL_Quit();
    }
    void pump() { SDL_UpdateJoysticks(); SDL_PumpEvents(); }
    void stimulus() {
        for (auto& pad : pads) pad.set({-32768, -32768}); pump();
        for (unsigned p = 0; p < 2; ++p) pads[p].set(held[p]); pump();
    }
    void finish() {
        for (auto& pad : pads) pad.cleanup();
        check(created == 2 && cleaned == 2, "virtual ownership cleanup incomplete");
        SDL_Quit(); initialized = false; check(SDL_WasInit(0) == 0, "SDL lifetime remained");
    }
};
struct Observation { std::string phase; unsigned pad; Pair before, after, mapped; Sint16 stick; bool button; };
} // namespace
int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "MW3_SDL_FAILURE:arguments\n"; return 2; }
    const std::string mode = argv[1], nonce = argv[2];
    const std::array<std::string_view, 5> modes{"baseline", "repaired", "wrong", "incomplete", "deadline"};
    if (std::find(modes.begin(), modes.end(), mode) == modes.end() || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= 'a' && c <= 'f') || (c >= '0' && c <= '9'); })) {
        std::cerr << "MW3_SDL_FAILURE:mode/nonce\n"; return 2;
    }
    try {
        const auto library = module(); check(SDL_GetVersion() == 3004014, "SDL version differs");
        std::cout << "MW3_SDL_LOADED:{\"nonce\":" << quote(nonce) << ",\"library\":" << quote(library) << ",\"version\":3004014}\n" << std::flush;
        Fixture fixture; std::vector<Observation> rows;
        auto capture = [&](const char* phase, unsigned p, Pair before) {
            auto& pad = fixture.pads[p];
            rows.push_back({phase, p, before, pad.sample(), pad.mapped(), SDL_GetGamepadAxis(pad.first, SDL_GAMEPAD_AXIS_LEFTX),
                SDL_GetGamepadButton(pad.first, static_cast<SDL_GamepadButton>(p))});
        };
        fixture.stimulus();
        for (unsigned p = 0; p < 2; ++p) { auto& pad = fixture.pads[p]; const auto before = pad.sample(); pad.open(); capture("initial", p, before); }
        for (unsigned p = 0; p < 2; ++p) { const auto before = fixture.pads[p].sample(); for (unsigned i = 0; i < 3; ++i) fixture.pump(); capture("unchanged", p, before); }
        for (unsigned p = 0; p < 2; ++p) { auto& pad = fixture.pads[p]; const auto before = pad.sample(); pad.second = SDL_OpenGamepad(pad.id); check(pad.second == pad.first, "second consumer handle"); capture("second", p, before); }
        fixture.stimulus();
        for (unsigned p = 0; p < 2; ++p) { auto& pad = fixture.pads[p]; const auto before = pad.sample(); pad.close(); pad.open(); capture("reopen", p, before); }
        fixture.stimulus();
        for (unsigned p = 0; p < 2; ++p) {
            auto& pad = fixture.pads[p]; const auto before = pad.sample();
            char* text = SDL_GetGamepadMapping(pad.first); check(text != nullptr, "actual mapping unavailable");
            std::string mapping = text; SDL_free(text);
            const auto first = mapping.find(','), second = mapping.find(',', first + 1);
            check(first != std::string::npos && second != std::string::npos, "mapping structure");
            mapping.replace(first + 1, second - first - 1, "MW3 modified original mapping " + std::to_string(p));
            check(SDL_AddGamepadMapping(mapping.c_str()) >= 0, "actual mapping replacement"); capture("remap", p, before);
        }
        for (auto& pad : fixture.pads) pad.set({-32768, -32768}); fixture.pump();
        for (unsigned p = 0; p < 2; ++p) capture("rest", p, fixture.pads[p].sample());
        fixture.stimulus();
        for (unsigned p = 0; p < 2; ++p) {
            auto& pad = fixture.pads[p]; const auto before = pad.sample();
            check(SDL_DetachVirtualJoystick(pad.id), "held detach"); pad.id = 0; capture("detach", p, before);
        }
        const bool baseline = rows.front().before[0] == 32767 && rows.front().after[0] == -32768 && rows.front().mapped[0] == 0;
        const bool wrong_rejected = rows.front().mapped[0] != 0;
        fixture.finish();
        std::cout << "MW3_SDL_READY:" << nonce << '\n' << std::flush;
        if (mode == "incomplete") return 0;
        std::cout << "MW3_SDL_COMPLETE:{\"schema\":1,\"mode\":" << quote(mode) << ",\"nonce\":" << quote(nonce)
            << ",\"library\":" << quote(library) << ",\"version\":3004014,\"created\":" << created << ",\"cleaned\":" << cleaned
            << ",\"sdl_after\":" << SDL_WasInit(0) << ",\"checks\":" << checks << ",\"rows\":[";
        for (std::size_t i = 0; i < rows.size(); ++i) {
            const auto& row = rows[i]; std::cout << (i ? "," : "") << "{\"phase\":" << quote(row.phase) << ",\"pad\":" << row.pad
                << ",\"before\":" << numbers(row.before) << ",\"after\":" << numbers(row.after) << ",\"mapped\":" << numbers(row.mapped)
                << ",\"stick\":" << row.stick << ",\"button\":" << (row.button ? "true" : "false") << '}';
        }
        std::cout << "]}\n" << std::flush;
        if (mode == "baseline") { check(baseline, "original defect not observed"); std::cerr << "MW3_SDL_FAILURE:original mapping reset observed\n"; return 1; }
        if (mode == "wrong") { check(wrong_rejected, "wrong expectation did not discriminate"); std::cerr << "MW3_SDL_FAILURE:wrong-zero expectation rejected\n"; return 1; }
        if (mode == "deadline") SDL_Delay(30000);
        return 0;
    } catch (const std::exception& error) { std::cerr << "MW3_SDL_FAILURE:" << error.what() << '\n'; return 1; }
}
