// SPDX-License-Identifier: GPL-3.0-only
// Original fixture mechanics from MW3-084, reused for real SDK user-routing probes.
#pragma once
#include <SDL3/SDL.h>
#include <rex/driver_context.h>
#include <rex/driver_module.h>
#include <rex/hid/input_driver.h>
#include <rex/logging/logger.h>
#include <rex/settings_registry.h>
#include <algorithm>
#include <array>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace h = rex::hid;
namespace {
unsigned checks = 0;
void Check(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}
template<class T> void Ok(const T& value, const char* message) { Check(bool(value), message); }
std::string Quote(std::string_view text) {
    std::string out = "\"";
    constexpr char digits[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += digits[c >> 4]; out += digits[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + '"';
}
std::string LoadedPath(const void* address) {
#ifdef _WIN32
    HMODULE module{};
    Check(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(address), &module) != 0, "loaded module lookup failed");
    std::array<wchar_t, 32768> path{};
    const auto n = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
    Check(n != 0 && n < path.size(), "loaded module path truncated");
    return std::filesystem::path(path.data()).generic_string();
#else
    Dl_info info{};
    Check(dladdr(address, &info) != 0 && info.dli_fname, "loaded module lookup failed");
    return std::filesystem::absolute(info.dli_fname).string();
#endif
}
std::string LoadedSDL() {
    // An import-library thunk may belong to this EXE. Resolve the loaded export.
#ifdef _WIN32
    const auto module = GetModuleHandleW(L"SDL3.dll");
    Check(module != nullptr, "loaded SDL library missing");
    const auto symbol = reinterpret_cast<const void*>(GetProcAddress(module, "SDL_GetVersion"));
#else
    const auto symbol = dlsym(RTLD_DEFAULT, "SDL_GetVersion");
#endif
    Check(symbol != nullptr, "loaded SDL export missing");
    return LoadedPath(symbol);
}
struct Library {
    void* handle{};
    explicit Library(const char* path) {
#ifdef _WIN32
        handle = reinterpret_cast<void*>(LoadLibraryW(std::filesystem::path(path).c_str()));
#else
        handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
#endif
        Check(handle != nullptr, "real input provider could not load");
    }
    rex::CreateInterfaceFn Factory() const {
#ifdef _WIN32
        auto fn = reinterpret_cast<rex::CreateInterfaceFn>(GetProcAddress(static_cast<HMODULE>(handle), rex::kCreateInterfaceSymbol));
#else
        auto fn = reinterpret_cast<rex::CreateInterfaceFn>(dlsym(handle, rex::kCreateInterfaceSymbol));
#endif
        Check(fn != nullptr, "provider factory missing");
        return fn;
    }
    ~Library() {
#ifdef _WIN32
        if (handle) FreeLibrary(static_cast<HMODULE>(handle));
#else
        if (handle) dlclose(handle);
#endif
    }
};
// A real owned single-thread event dispatcher, not a success-valued no-op.
struct Dispatcher final : rex::IDriverContext {
    const std::thread::id owner = std::this_thread::get_id();
    std::vector<rex::MoveOnlyFunction<void()>> pending;
    rex::ISettingsRegistry& GetSettingsRegistry() override { return rex::GetSettingsRegistry(); }
    rex::ILogger& GetLogger() override { return rex::GetLogger(); }
    rex::Result<void> RunOnUIThread(rex::MoveOnlyFunction<void()> fn) override {
        if (std::this_thread::get_id() != owner) return rex::Err(rex::ErrorCategory::kPlatform, "not the owned polling thread");
        fn();
        return rex::Ok();
    }
    void PostToUIThread(rex::MoveOnlyFunction<void()> fn) override {
        Check(std::this_thread::get_id() == owner && pending.size() < 64, "dispatcher ownership/budget violation");
        pending.push_back(std::move(fn));
    }
    void Drain() {
        for (unsigned pass = 0; !pending.empty(); ++pass) {
            Check(pass < 64, "dispatcher failed to quiesce");
            auto work = std::move(pending);
            pending.clear();
            for (auto& fn : work) fn();
        }
    }
};
struct VirtualPad {
    std::string name;
    SDL_JoystickID instance{};
    SDL_Joystick* joystick{};
    unsigned cleaned{}, rumbles{};
    Uint16 low{}, high{};
    static void SDLCALL Cleanup(void* data) { ++static_cast<VirtualPad*>(data)->cleaned; }
    static bool SDLCALL Rumble(void* data, Uint16 low, Uint16 high) {
        auto& pad = *static_cast<VirtualPad*>(data);
        ++pad.rumbles; pad.low = low; pad.high = high;
        return true;
    }
    void Attach(std::size_t i) {
        name = "MW3 original virtual pad " + std::to_string(i);
        SDL_VirtualJoystickDesc desc{};
        SDL_INIT_INTERFACE(&desc);
        desc.type = SDL_JOYSTICK_TYPE_GAMEPAD;
        // Distinct original virtual GUIDs; names alone can share an SDL mapping.
        desc.vendor_id = 0xffff;
        desc.product_id = static_cast<Uint16>(i + 1);
        desc.naxes = SDL_GAMEPAD_AXIS_COUNT;
        desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
        desc.axis_mask = (1u << SDL_GAMEPAD_AXIS_COUNT) - 1;
        desc.button_mask = (1u << SDL_GAMEPAD_BUTTON_COUNT) - 1;
        desc.name = name.c_str(); desc.userdata = this;
        desc.Rumble = Rumble; desc.Cleanup = Cleanup;
        instance = SDL_AttachVirtualJoystick(&desc);
        Check(instance != 0 && SDL_IsJoystickVirtual(instance), "original virtual device attach failed");
        joystick = SDL_OpenJoystick(instance);
        Check(joystick != nullptr, "original virtual handle open failed");
        Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, -32768), "trigger baseline failed");
        Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, -32768), "trigger baseline failed");
    }
    void Detach() {
        if (instance) { Ok(SDL_DetachVirtualJoystick(instance), "owned virtual detach failed"); instance = 0; }
        if (joystick) { SDL_CloseJoystick(joystick); joystick = nullptr; }
    }
};
bool Same(const h::PadState& a, const h::PadState& b) {
    return a.buttons == b.buttons && a.left_trigger == b.left_trigger && a.right_trigger == b.right_trigger &&
        a.thumb_lx == b.thumb_lx && a.thumb_ly == b.thumb_ly && a.thumb_rx == b.thumb_rx && a.thumb_ry == b.thumb_ry;
}
} // namespace
