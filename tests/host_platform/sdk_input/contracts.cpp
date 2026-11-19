// SPDX-License-Identifier: GPL-3.0-only
// Original virtual-device observations through the real private SDK provider.
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
struct EmptyFactory final : rex::IInterfaceFactory {
    rex::IInterface* Find(std::string_view, u32) override { return nullptr; }
    std::vector<rex::IInterface*> FindAll(std::string_view, u32) override { return {}; }
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
struct Fixture {
    Library library;
    EmptyFactory factory;
    Dispatcher dispatcher;
    rex::IModule* module{};
    std::unique_ptr<h::IInputDriver> driver;
    std::array<VirtualPad, 4> pads{};
    std::array<h::PadDeviceID, 4> ids{};
    std::string provider_path;
    bool connected{}, inited{}, running{}, sdl{};
    explicit Fixture(const char* provider) : library(provider) {
      try {
        // Disable physical backends before any joystick initialization.
        for (const char* hint : {SDL_HINT_JOYSTICK_HIDAPI, SDL_HINT_JOYSTICK_RAWINPUT,
             SDL_HINT_JOYSTICK_DIRECTINPUT, SDL_HINT_JOYSTICK_WGI, SDL_HINT_XINPUT_ENABLED,
             SDL_HINT_JOYSTICK_IOKIT, SDL_HINT_JOYSTICK_LINUX_CLASSIC}) SDL_SetHint(hint, "0");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        Check(SDL_WasInit(0) == 0, "SDL state was not private and fresh");
        Ok(SDL_Init(SDL_INIT_GAMEPAD), "private SDL initialization failed"); sdl = true;
        int count = -1;
        auto* initial = SDL_GetJoysticks(&count);
        SDL_free(initial);
        Check(count == 0, "unexpected devices present; no external device may be exercised");
        auto create = library.Factory();
        module = static_cast<rex::IModule*>(create(rex::IModule::kInterface.name, rex::IModule::kInterface.version));
        auto* drivers = static_cast<rex::IDriverModule*>(create(rex::IDriverModule::kInterface.name, rex::IDriverModule::kInterface.version));
        Check(module && drivers, "real provider interfaces missing");
        Ok(module->Connect(factory), "provider connect failed"); connected = true;
        Ok(module->Init(), "provider init failed"); inited = true;
        for (const auto& registration : drivers->GetDrivers()) {
            if (registration.type == rex::DriverType::kInput && registration.name == "sdl3") {
                Check(!driver, "ambiguous SDL3 registration");
                provider_path = LoadedPath(reinterpret_cast<const void*>(registration.create));
                auto raw = registration.create();
                driver.reset(static_cast<h::IInputDriver*>(raw.release()));
            }
        }
        Check(bool(driver), "real SDL3 driver registration missing");
        Ok(rex::GetSettingsRegistry().SetText(rex::SettingLayer::kTitle, "hid.sdl.mappings_file", ""), "mapping isolation failed");
        Ok(driver->Initialize(dispatcher), "real driver Initialize failed"); running = true;
        for (std::size_t i = 0; i < pads.size(); ++i) pads[i].Attach(i);
        Pump(); Identify();
      } catch (...) { Cleanup(); throw; }
    }
    void Pump() {
        SDL_UpdateJoysticks(); SDL_PumpEvents(); dispatcher.Drain();
    }
    std::vector<h::PadDevice> Devices() {
        std::vector<h::PadDevice> devices;
        driver->EnumerateDevices(devices); dispatcher.Drain();
        driver->EnumerateDevices(devices);
        return devices;
    }
    void Identify() {
        const auto devices = Devices();
        Check(devices.size() == 4, "not exactly four owned virtual devices");
        for (std::size_t i = 0; i < pads.size(); ++i) {
            auto it = std::find_if(devices.begin(), devices.end(), [&](const auto& d) { return d.name == pads[i].name; });
            if (it == devices.end()) {
                for (const auto& d : devices) std::cerr << "MW3_INPUT_DEVICE:name=" << Quote(d.name) << " id=" << d.id.value << " vendor=" << d.info.vendor << " product=" << d.info.product << '\n';
            }
            Check(it != devices.end() && it->id.value != 0, "virtual identity missing");
            ids[i] = it->id;
            for (std::size_t j = 0; j < i; ++j) Check(ids[j] != ids[i], "duplicate raw device identity");
        }
    }
    h::PadState Read(std::size_t i) {
        auto state = driver->GetDeviceState(ids[i]); Ok(state, "owned state unavailable");
        return *state;
    }
    void State(bool wrong = false) {
        constexpr std::array<u16, 4> buttons{h::kPadA, h::kPadB, h::kPadX, h::kPadY};
        for (std::size_t i = 0; i < pads.size(); ++i) {
            auto* joystick = pads[i].joystick;
            Ok(SDL_SetJoystickVirtualButton(joystick, static_cast<int>(i), true), "virtual button update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, static_cast<Sint16>((i + 1) * 1024)), "virtual x update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTY, -32768), "virtual y update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTX, static_cast<Sint16>(-static_cast<int>((i + 1) * 1024))), "virtual rx update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTY, 32767), "virtual ry update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, 32767), "virtual trigger update failed");
        }
        Pump();
        for (std::size_t i = 0; i < pads.size(); ++i) {
            const auto state = Read(i);
            if (wrong && i == 0) Check(state.buttons == h::kPadB, "deliberate wrong-result rejected");
            Check(state.buttons == buttons[i], "independent buttons lost");
            Check(state.thumb_lx == static_cast<int>((i + 1) * 1024) && state.thumb_rx == -static_cast<int>((i + 1) * 1024), "independent sticks lost");
            Check(state.thumb_ly == 32767 && state.thumb_ry == -32768, "full-range vertical mapping differs");
            Check(state.left_trigger == 0 && state.right_trigger == 255, "trigger endpoints differ");
        }
    }
    void Capabilities() {
        for (std::size_t i = 0; i < pads.size(); ++i) {
            auto caps = driver->GetDeviceCapabilities(ids[i]); Ok(caps, "capabilities unavailable");
            Check((caps->supported.buttons & h::kPadA) != 0 && caps->motors.left_motor == 65535 && caps->motors.right_motor == 65535, "virtual capabilities differ");
            const auto before = pads[i].rumbles;
            Ok(driver->SetDeviceVibration(ids[i], {1234, 4321}), "owned virtual rumble rejected");
            Check(pads[i].rumbles > before && pads[i].low == 1234 && pads[i].high == 4321, "virtual rumble mapping differs");
        }
        for (h::PadDeviceID id : {h::PadDeviceID{}, h::PadDeviceID{std::numeric_limits<u64>::max()}}) {
            auto state = driver->GetDeviceState(id); auto caps = driver->GetDeviceCapabilities(id);
            auto motors = driver->SetDeviceVibration(id, {1, 1});
            Check(!state && state.error().category == rex::ErrorCategory::kNotFound, "invalid state ID accepted");
            Check(!caps && caps.error().category == rex::ErrorCategory::kNotFound, "invalid capability ID accepted");
            Check(!motors && motors.error().category == rex::ErrorCategory::kNotFound, "invalid vibration ID accepted");
        }
    }
    void Reconnect() {
        State();
        std::array<h::PadState, 4> before{};
        for (std::size_t i = 0; i < 4; ++i) before[i] = Read(i);
        const auto old = ids[1]; const auto old_instance = pads[1].instance;
        const auto revision = driver->GetDeviceRevision(); dispatcher.Drain();
        pads[1].Detach(); Pump();
        Check(Devices().size() == 3 && driver->GetDeviceRevision() != revision, "disconnect enumeration/revision failed");
        auto stale = driver->GetDeviceState(old);
        Check(!stale && stale.error().category == rex::ErrorCategory::kNotFound, "disconnected raw ID revived");
        for (std::size_t i : {0u, 2u, 3u}) Check(Same(Read(i), before[i]), "disconnect changed another device");
        pads[1].Attach(1); Pump(); Identify();
        Check(ids[1] != old, "reconnect reused a raw device ID");
        SDL_Event late{}; late.type = SDL_EVENT_GAMEPAD_BUTTON_DOWN;
        late.gbutton.which = old_instance; late.gbutton.button = SDL_GAMEPAD_BUTTON_SOUTH; late.gbutton.down = true;
        Ok(SDL_PushEvent(&late), "late synthetic event injection failed"); Pump();
        Check(Read(1).buttons == 0, "late removed-instance event reached replacement");
        for (std::size_t i : {0u, 2u, 3u}) Check(Same(Read(i), before[i]), "late event changed another device");
        stale = driver->GetDeviceState(old);
        Check(!stale && stale.error().category == rex::ErrorCategory::kNotFound, "old ID accepted after reconnect");
    }
    unsigned Finish() {
        for (auto& pad : pads) pad.Detach();
        Pump(); Check(Devices().empty(), "virtual devices survived detach");
        driver->Shutdown(); running = false; dispatcher.Drain();
        Check(dispatcher.pending.empty(), "owned dispatch remained pending");
        auto stopped = driver->GetDeviceState(ids[0]);
        Check(!stopped && stopped.error().category == rex::ErrorCategory::kNotFound, "stopped driver accepted a device");
        Check(driver->GetDeviceRevision() == 0, "stopped driver retained revision");
        driver.reset();
        module->Shutdown(); inited = false; module->Disconnect(); connected = false;
        unsigned cleaned = 0;
        for (const auto& pad : pads) cleaned += pad.cleaned;
        Check(cleaned == 4 || cleaned == 5, "owned virtual handle cleanup incomplete");
        SDL_Quit(); sdl = false;
        Check(SDL_WasInit(0) == 0, "SDL subsystem ownership leaked");
        return cleaned;
    }
    void Cleanup() {
        // Failure cleanup acts exclusively on fixture-owned IDs and handles.
        for (auto& pad : pads) {
            if (pad.instance) SDL_DetachVirtualJoystick(pad.instance);
            if (pad.joystick) SDL_CloseJoystick(pad.joystick);
        }
        if (driver && running) driver->Shutdown();
        dispatcher.Drain(); driver.reset();
        if (module && inited) module->Shutdown();
        if (module && connected) module->Disconnect();
        if (sdl) SDL_Quit();
    }
    ~Fixture() { Cleanup(); }
};
} // namespace

int main(int argc, char** argv) {
    if (argc != 4 && argc != 5) { std::cerr << "MW3_INPUT_FAILURE:arguments required\n"; return 2; }
    const std::string_view name = argv[1], nonce = argv[2];
    const bool wrong = argc == 5 && std::string_view(argv[4]) == "--wrong-result";
    if ((name != "four-devices" && name != "state" && name != "reconnect" && name != "lifetime") ||
        nonce.size() != 32 || !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
        (argc == 5 && !wrong)) { std::cerr << "MW3_INPUT_FAILURE:invalid case or nonce\n"; return 2; }
    try {
        std::string provider;
        const auto sdl = LoadedSDL();
        const auto base = LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger));
        const unsigned cycles = name == "lifetime" ? 4 : 1;
        unsigned cleaned = 0;
        for (unsigned cycle = 0; cycle < cycles; ++cycle) {
            Fixture fixture(argv[3]); provider = fixture.provider_path;
            fixture.Capabilities();
            if (name == "state" || name == "lifetime") fixture.State(wrong);
            if (name == "reconnect") fixture.Reconnect();
            cleaned += fixture.Finish();
        }
        std::cout << "MW3_INPUT_COMPLETE:{\"schema\":1,\"case\":" << Quote(name) << ",\"nonce\":" << Quote(nonce)
            << ",\"cycles\":" << cycles << ",\"devices\":4,\"cleaned\":" << cleaned << ",\"pending\":0,\"sdl_init_after\":0,\"checks\":" << checks
            << ",\"sdl_version\":" << SDL_GetVersion() << ",\"loaded\":{\"provider\":" << Quote(provider)
            << ",\"sdl\":" << Quote(sdl) << ",\"base\":" << Quote(base) << "}}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_INPUT_FAILURE:" << error.what() << '\n'; return 1;
    }
}
