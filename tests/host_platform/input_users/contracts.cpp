// SPDX-License-Identifier: GPL-3.0-only
#include "fixture.hpp"
#include <rex/app_info.h>
#include <rex/hid/input_system.h>
#include <optional>
#include <utility>

namespace {
struct HostInfo final : rex::IAppInfo {
    rex::AppSysRequirements needs{};
    HostInfo() { needs.input = true; }
    const rex::AppSysRequirements& GetRequirements() const override { return needs; }
    std::string_view GetAppName() const override { return "mw3_original_input_users"; }
};
struct HostFactory final : rex::IInterfaceFactory {
    Dispatcher& dispatch;
    HostInfo& info;
    rex::IDriverModule* provider{};
    HostFactory(Dispatcher& context, HostInfo& app) : dispatch(context), info(app) {}
    template<class T> static rex::IInterface* Match(std::string_view name, u32 version, T* value) {
        return name == T::kInterface.name && version == T::kInterface.version ? value : nullptr;
    }
    rex::IInterface* Find(std::string_view name, u32 version) override {
        if (auto* p = Match<rex::IDriverContext>(name, version, &dispatch)) return p;
        if (auto* p = Match<rex::IAppInfo>(name, version, &info)) return p;
        if (auto* p = Match<rex::ISettingsRegistry>(name, version, &rex::GetSettingsRegistry())) return p;
        if (auto* p = Match<rex::ILogger>(name, version, &rex::GetLogger())) return p;
        return Match<rex::IDriverModule>(name, version, provider);
    }
    std::vector<rex::IInterface*> FindAll(std::string_view name, u32 version) override {
        auto* p = Find(name, version);
        return p ? std::vector<rex::IInterface*>{p} : std::vector<rex::IInterface*>{};
    }
};
bool Neutral(const h::PadState& state) { return Same(state, h::PadState{}); }
constexpr std::array<u16, 4> buttons{h::kPadA, h::kPadB, h::kPadX, h::kPadY};

struct Fixture {
    Library input_library, provider_library;
    Dispatcher dispatch;
    HostInfo app;
    HostFactory factory{dispatch, app};
    rex::IModule *input{}, *provider{};
    h::IInputSystem* system{};
    std::optional<rex::ScopeGuard> subscription;
    std::array<VirtualPad, 4> pads{};
    std::vector<std::pair<u32, bool>> connections;
    unsigned created{}, reentries{}, ui_depth{};
    bool sdl{}, input_connected{}, provider_connected{}, input_inited{}, provider_inited{};
    std::string input_path, provider_path;

    Fixture(const char* input_file, const char* provider_file, bool shared)
        : input_library(input_file), provider_library(provider_file) {
      try {
        for (const char* hint : {SDL_HINT_JOYSTICK_HIDAPI, SDL_HINT_JOYSTICK_RAWINPUT,
             SDL_HINT_JOYSTICK_DIRECTINPUT, SDL_HINT_JOYSTICK_WGI, SDL_HINT_XINPUT_ENABLED,
             SDL_HINT_JOYSTICK_IOKIT, SDL_HINT_JOYSTICK_LINUX_CLASSIC}) SDL_SetHint(hint, "0");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        Check(SDL_WasInit(0) == 0, "SDL state is not fresh");
        Ok(SDL_Init(SDL_INIT_GAMEPAD), "private SDL init failed"); sdl = true;
        int count = -1;
        auto* initial = SDL_GetJoysticks(&count); SDL_free(initial);
        Check(count == 0, "unexpected devices; external input must not be used");
        auto make_input = input_library.Factory(), make_provider = provider_library.Factory();
        input_path = LoadedPath(reinterpret_cast<const void*>(make_input));
        provider_path = LoadedPath(reinterpret_cast<const void*>(make_provider));
        input = static_cast<rex::IModule*>(make_input(rex::IModule::kInterface.name, rex::IModule::kInterface.version));
        provider = static_cast<rex::IModule*>(make_provider(rex::IModule::kInterface.name, rex::IModule::kInterface.version));
        factory.provider = static_cast<rex::IDriverModule*>(make_provider(rex::IDriverModule::kInterface.name, rex::IDriverModule::kInterface.version));
        system = static_cast<h::IInputSystem*>(make_input(h::IInputSystem::kInterface.name, h::IInputSystem::kInterface.version));
        Check(input && provider && factory.provider && system, "real versioned input interfaces missing");
        auto& registry = rex::GetSettingsRegistry();
        for (const auto& setting : std::array<std::pair<const char*, const char*>, 6>{{
             {"hid.drivers", "sdl3"}, {"hid.sdl.mappings_file", ""}, {"hid.mnk_mode", "false"},
             {"hid.guide_button", "false"}, {"hid.left_stick_deadzone", "0"}, {"hid.right_stick_deadzone", "0"}}}) {
            Ok(registry.SetText(rex::SettingLayer::kTitle, setting.first, setting.second), "private setting failed");
        }
        Ok(registry.SetText(rex::SettingLayer::kTitle, "hid.shared_pads", shared ? "true" : "false"), "shared setting failed");
        Ok(provider->Connect(factory), "provider Connect failed"); provider_connected = true;
        Ok(input->Connect(factory), "input-system Connect failed"); input_connected = true;
        Ok(provider->Init(), "provider Init failed"); provider_inited = true;
        Ok(input->Init(), "input-system Init failed"); input_inited = true;
        Check(system->GetSettings().drivers.Get() == "sdl3" && system->GetSettings().shared_pads.Get() == shared &&
              !system->GetSettings().mnk_mode.Get(), "selected driver/policy differs");
        subscription.emplace(system->OnConnectionChange([this](u32 user, bool connected) {
            Check(user < 4 && std::this_thread::get_id() == dispatch.owner, "connection callback ownership differs");
            connections.emplace_back(user, connected);
            (void)system->GetState(user); // SDK promises callbacks run without its input lock.
            ++reentries;
        }));
      } catch (...) { Cleanup(); throw; }
    }
    void Pump() { SDL_UpdateJoysticks(); SDL_PumpEvents(); dispatch.Drain(); }
    void Attach(const std::array<std::size_t, 4>& order, bool discover = true) {
        for (auto i : order) { pads[i].Attach(i); ++created; }
        Pump();
        int count = -1; auto* ids = SDL_GetJoysticks(&count); SDL_free(ids);
        Check(count == 4, "four owned virtual devices not present");
        if (discover) {
            for (u32 user = 0; user < 4; ++user) (void)system->GetState(user);
            Pump();
        }
    }
    h::IInputSystem::PadReading Read(u32 user) {
        auto value = system->GetState(user); Ok(value, "SDK user reading unavailable");
        return *value;
    }
    std::array<std::size_t, 4> Routes() {
        std::array<std::size_t, 4> routes{};
        for (u32 user = 0; user < 4; ++user) {
            (void)Read(user);
            auto info = system->GetPadInfo(user); Ok(info, "SDK user pad info unavailable");
            Check(info->vendor == 0xffff && info->product >= 1 && info->product <= 4, "user route is not an owned virtual pad");
            routes[user] = info->product - 1;
            for (u32 previous = 0; previous < user; ++previous) Check(routes[user] != routes[previous], "SDK users share a device unexpectedly");
        }
        return routes;
    }
    void SetButtons(bool down) {
        for (std::size_t i = 0; i < 4; ++i) Ok(SDL_SetJoystickVirtualButton(pads[i].joystick, static_cast<int>(i), down), "original button update failed");
        Pump();
    }
    void Controls() {
        for (std::size_t i = 0; i < 4; ++i) {
            auto* p = pads[i].joystick;
            Ok(SDL_SetJoystickVirtualButton(p, static_cast<int>(i), true), "original button update failed");
            Ok(SDL_SetJoystickVirtualAxis(p, SDL_GAMEPAD_AXIS_LEFTX, static_cast<Sint16>((i + 1) * 1024)), "original stick update failed");
            Ok(SDL_SetJoystickVirtualAxis(p, SDL_GAMEPAD_AXIS_LEFTY, -32768), "original y update failed");
            Ok(SDL_SetJoystickVirtualAxis(p, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, 32767), "original trigger update failed");
        }
        Pump();
    }
    void Fallback() {
        const auto value = Read(0);
        Check(Neutral(value.state), "no-device user0 is not neutral fallback");
        auto info = system->GetPadInfo(0);
        Check(!info && info.error().category == rex::ErrorCategory::kNotFound, "fallback masquerades as an assigned controller");
        Ok(system->GetCapabilities(0), "documented fallback capabilities missing");
        Check(connections.empty(), "neutral fallback counted as a real connection");
        for (u32 user = 1; user < 4; ++user) {
            Check(!system->GetState(user) && !system->GetCapabilities(user), "fallback fabricated another user");
        }
        Check(Read(0).packet == value.packet, "unchanged fallback packet changed");
    }
    void Users(bool wrong = false) {
        Controls(); const auto routes = Routes(); Pump();
        std::array<h::IInputSystem::PadReading, 4> readings{};
        for (u32 user = 0; user < 4; ++user) {
            const auto index = routes[user]; readings[user] = Read(user);
            Check(SDL_GetJoystickButton(pads[index].joystick, static_cast<int>(index)) &&
                  SDL_GetJoystickAxis(pads[index].joystick, SDL_GAMEPAD_AXIS_LEFTX) == static_cast<int>((index + 1) * 1024),
                  "original SDL stimulus is not held");
            if (wrong && user == 0) Check(readings[user].state.buttons == buttons[(index + 1) % 4], "deliberate wrong-routing rejected");
            if (readings[user].state.buttons != buttons[index] || readings[user].state.thumb_lx != static_cast<int>((index + 1) * 1024)) {
                std::cerr << "MW3_USERS_READING:user=" << user << " product=" << index + 1 << " buttons=" << readings[user].state.buttons
                          << " x=" << readings[user].state.thumb_lx << " expected_buttons=" << buttons[index]
                          << " source_button=" << SDL_GetJoystickButton(pads[index].joystick, static_cast<int>(index))
                          << " source_x=" << SDL_GetJoystickAxis(pads[index].joystick, SDL_GAMEPAD_AXIS_LEFTX) << '\n';
            }
            Check(readings[user].state.buttons == buttons[index] && readings[user].state.thumb_lx == static_cast<int>((index + 1) * 1024), "independent user state routed incorrectly");
            Check(readings[user].state.thumb_ly == 32767 && readings[user].state.right_trigger == 255, "user axis/trigger mapping differs");
            Check(Read(user).packet == readings[user].packet, "unchanged user packet changed");
            auto caps = system->GetCapabilities(user); Ok(caps, "owned user capabilities missing");
            Check((caps->supported.buttons & h::kPadA) != 0 && (caps->supported.buttons & h::kPadGuide) == 0, "user capability filtering differs");
            const auto before = pads[index].rumbles;
            Ok(system->SetVibration(user, {static_cast<u16>(1000 + user), static_cast<u16>(2000 + user)}), "user vibration rejected");
            Check(pads[index].rumbles > before && pads[index].low == 1000 + user && pads[index].high == 2000 + user, "user vibration reached the wrong device");
        }
        const auto changed_index = routes[2];
        Ok(SDL_SetJoystickVirtualButton(pads[changed_index].joystick, static_cast<int>(changed_index), false), "packet mutation failed"); Pump();
        for (u32 user = 0; user < 4; ++user) {
            const auto next = Read(user);
            if (user == 2) Check(next.packet != readings[user].packet && next.state.buttons == 0, "changed user packet/state not updated");
            else Check(next.packet == readings[user].packet && Same(next.state, readings[user].state), "one device changed another SDK user");
        }
        for (u32 user : {4u, 0xffu, std::numeric_limits<u32>::max()}) {
            auto state = system->GetState(user); auto caps = system->GetCapabilities(user); auto rumble = system->SetVibration(user, {1, 1});
            Check(!state && state.error().category == rex::ErrorCategory::kNotFound, "invalid SDK user state accepted");
            Check(!caps && !rumble, "invalid SDK user capability/vibration accepted");
        }
    }
    void Blocking() {
        Controls(); (void)Routes();
        std::array<h::IInputSystem::PadReading, 4> before{}, blocked{};
        for (u32 user = 0; user < 4; ++user) before[user] = Read(user);
        system->AcquireUIBlock(); ++ui_depth; system->AcquireUIBlock(); ++ui_depth;
        for (u32 user = 0; user < 4; ++user) {
            blocked[user] = Read(user);
            Check(Neutral(blocked[user].state) && blocked[user].packet != before[user].packet, "UI block did not neutralize user");
            Check(Read(user).packet == blocked[user].packet, "unchanged blocked packet changed");
        }
        system->ReleaseUIBlock(); --ui_depth;
        for (u32 user = 0; user < 4; ++user) Check(Neutral(Read(user).state), "nested block released too early");
        system->ReleaseUIBlock(); --ui_depth;
        for (u32 user = 0; user < 4; ++user) {
            const auto restored = Read(user);
            Check(restored.state.buttons == 0 && restored.state.thumb_lx == before[user].state.thumb_lx &&
                  restored.state.right_trigger == before[user].state.right_trigger, "unblock axis restoration/held-button consumption differs");
        }
        SetButtons(false); for (u32 user = 0; user < 4; ++user) (void)Read(user);
        SetButtons(true); const auto routes = Routes();
        for (u32 user = 0; user < 4; ++user) Check(Read(user).state.buttons == buttons[routes[user]], "fresh press remained consumed after UI block");
    }
    void Hotplug() {
        Controls(); const auto routes = Routes();
        std::array<h::IInputSystem::PadReading, 4> before{};
        for (u32 user = 0; user < 4; ++user) before[user] = Read(user);
        connections.clear(); const auto index = routes[1]; const auto old_instance = pads[index].instance;
        pads[index].Detach(); Pump();
        Check(!system->GetState(1), "disconnected nonzero user still has a pad");
        for (u32 user : {0u, 2u, 3u}) Check(Same(Read(user).state, before[user].state), "disconnect reassigned another user");
        Check(std::find(connections.begin(), connections.end(), std::pair<u32, bool>{1, false}) != connections.end(), "missing disconnection callback");
        pads[index].Attach(index); ++created; Pump();
        Check(Read(1).state.buttons == 0, "reconnected pad retained held state");
        Check(Routes() == routes, "hole refill changed other SDK user routes");
        SDL_Event late{}; late.type = SDL_EVENT_GAMEPAD_BUTTON_DOWN; late.gbutton.which = old_instance;
        late.gbutton.button = SDL_GAMEPAD_BUTTON_SOUTH; late.gbutton.down = true;
        Ok(SDL_PushEvent(&late), "late owned event injection failed"); Pump();
        Check(Read(1).state.buttons == 0, "late removed-instance event reached replacement user");
        Check(std::find(connections.begin(), connections.end(), std::pair<u32, bool>{1, true}) != connections.end() && reentries > 0, "reconnect or reentrant callback missing");
        for (u32 user : {0u, 2u, 3u}) Check(Same(Read(user).state, before[user].state), "reconnect changed another user");
    }
    void Shared() {
        Controls();
        const auto reading = Read(0);
        Check(reading.state.buttons == static_cast<u16>(h::kPadA | h::kPadB | h::kPadX | h::kPadY), "explicit shared-pad policy did not merge buttons");
        for (u32 user = 1; user < 4; ++user) Check(!system->GetState(user), "shared mode fabricated independent users");
        auto info = system->GetPadInfo(0); Ok(info, "shared active device info missing");
        Check(info->vendor == 0xffff && info->product >= 1 && info->product <= 4, "shared active pad is not owned");
        Check(Read(0).packet == reading.packet, "unchanged merged packet changed");
    }
    unsigned Finish() {
        Check(ui_depth == 0, "UI blocks unbalanced"); subscription.reset();
        for (auto& pad : pads) pad.Detach(); Pump();
        Check(Neutral(Read(0).state), "final no-device reading not neutral");
        for (u32 user = 1; user < 4; ++user) Check(!system->GetState(user), "device survived teardown");
        input->Shutdown(); input_inited = false; dispatch.Drain();
        Check(!system->GetState(0), "stopped input system returned a successful fallback");
        input->Disconnect(); input_connected = false;
        provider->Shutdown(); provider_inited = false; provider->Disconnect(); provider_connected = false;
        unsigned cleaned = 0; for (const auto& pad : pads) cleaned += pad.cleaned;
        Check(cleaned == created && dispatch.pending.empty(), "virtual cleanup/dispatcher ownership leaked");
        SDL_Quit(); sdl = false; Check(SDL_WasInit(0) == 0, "SDL subsystem leaked");
        return cleaned;
    }
    void Cleanup() {
        subscription.reset();
        if (system) while (ui_depth) { system->ReleaseUIBlock(); --ui_depth; }
        for (auto& pad : pads) {
            if (pad.instance) SDL_DetachVirtualJoystick(pad.instance);
            if (pad.joystick) SDL_CloseJoystick(pad.joystick);
        }
        if (input && input_inited) input->Shutdown(); dispatch.Drain();
        if (input && input_connected) input->Disconnect();
        if (provider && provider_inited) provider->Shutdown();
        if (provider && provider_connected) provider->Disconnect();
        if (sdl) SDL_Quit();
    }
    ~Fixture() { Cleanup(); }
};
} // namespace

int main(int argc, char** argv) {
    if (argc != 5 && argc != 6) { std::cerr << "MW3_USERS_FAILURE:arguments required\n"; return 2; }
    const std::string_view name = argv[1], nonce = argv[2];
    const bool wrong = argc == 6 && std::string_view(argv[5]) == "--wrong-routing";
    const std::array cases{"fallback", "users", "hotplug", "blocking", "shared", "orders", "held-discovery"};
    if (std::find(cases.begin(), cases.end(), name) == cases.end() || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
        (argc == 6 && (!wrong || name != "users"))) { std::cerr << "MW3_USERS_FAILURE:invalid case or nonce\n"; return 2; }
    try {
        const auto sdl = LoadedSDL(), base = LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger));
        std::string input, provider;
        unsigned cycles = 0, created = 0, cleaned = 0;
        std::array<std::size_t, 4> order = name == "orders" ? std::array<std::size_t, 4>{0, 1, 2, 3} : std::array<std::size_t, 4>{2, 0, 3, 1};
        do {
            Fixture fixture(argv[3], argv[4], name == "shared");
            input = fixture.input_path; provider = fixture.provider_path;
            if (cycles == 0) {
                std::cout << "MW3_USERS_LOADED:{\"schema\":1,\"nonce\":" << Quote(nonce)
                    << ",\"loaded\":{\"input\":" << Quote(input) << ",\"provider\":" << Quote(provider)
                    << ",\"sdl\":" << Quote(sdl) << ",\"base\":" << Quote(base) << "}}" << std::endl;
            }
            if (name == "fallback") fixture.Fallback();
            else {
                fixture.Attach(order, name != "held-discovery");
                if (name == "users" || name == "orders" || name == "held-discovery") fixture.Users(wrong);
                else if (name == "hotplug") fixture.Hotplug();
                else if (name == "blocking") fixture.Blocking();
                else if (name == "shared") fixture.Shared();
            }
            created += fixture.created; cleaned += fixture.Finish(); ++cycles;
        } while (name == "orders" && std::next_permutation(order.begin(), order.end()));
        const unsigned routed = name == "fallback" ? 0 : name == "shared" ? 1 : 4;
        std::cout << "MW3_USERS_COMPLETE:{\"schema\":1,\"case\":" << Quote(name) << ",\"nonce\":" << Quote(nonce)
            << ",\"cycles\":" << cycles << ",\"created\":" << created << ",\"cleaned\":" << cleaned
            << ",\"routed_users\":" << routed << ",\"readable_users\":" << (name == "fallback" ? 1 : routed)
            << ",\"pending\":0,\"blocks\":0,\"sdl_init_after\":0,\"checks\":" << checks
            << ",\"sdl_version\":" << SDL_GetVersion() << ",\"loaded\":{\"input\":" << Quote(input)
            << ",\"provider\":" << Quote(provider) << ",\"sdl\":" << Quote(sdl) << ",\"base\":" << Quote(base) << "}}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_USERS_FAILURE:" << error.what() << '\n'; return 1;
    }
}
