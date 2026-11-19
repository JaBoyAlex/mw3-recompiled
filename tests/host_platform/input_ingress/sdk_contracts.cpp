// SPDX-License-Identifier: GPL-3.0-only
// The runner stages the unchanged MW3-084 original host helpers beside this file.
#define main mw3_original_raw_input_main
#include "baseline-contracts.cpp"
#undef main
#include "input/ingress/ingress.hpp"
#include <cmath>

namespace in = mw3::input;
namespace {
constexpr std::array<std::size_t, 4> owner_slot{2, 0, 3, 1};
constexpr std::array<in::OwnerId, 4> owner_id{101, 203, 307, 409};
constexpr std::array<u16, 4> sdk_face{h::kPadA, h::kPadB, h::kPadX, h::kPadY};
struct Loaded {
    std::string provider, sdl, base;
    bool operator==(const Loaded&) const = default;
};
void EmitLoaded(std::string_view nonce, const Loaded& loaded) {
    std::cout << "MW3_INGRESS_LOADED:{\"schema\":1,\"nonce\":" << Quote(nonce)
        << ",\"loaded\":{\"provider\":" << Quote(loaded.provider) << ",\"sdl\":" << Quote(loaded.sdl)
        << ",\"base\":" << Quote(loaded.base) << "}}\n" << std::flush;
}

// Owns only original process-local devices, one driver and an actual UI dispatcher.
struct Session {
    std::array<VirtualPad, 4> pads{}; // Callback storage outlives driver/library.
    Library library;
    Dispatcher dispatch;
    EmptyFactory factory;
    rex::IModule* module{};
    std::unique_ptr<h::IInputDriver> driver;
    std::array<h::PadDeviceID, 4> ids{};
    Loaded loaded;
    unsigned created{};
    bool sdl{}, connected{}, initialized{}, running{};
    explicit Session(const char* file) : library(file) {
      try {
        for (const char* hint : {SDL_HINT_JOYSTICK_HIDAPI, SDL_HINT_JOYSTICK_RAWINPUT,
             SDL_HINT_JOYSTICK_DIRECTINPUT, SDL_HINT_JOYSTICK_WGI, SDL_HINT_XINPUT_ENABLED,
             SDL_HINT_JOYSTICK_IOKIT, SDL_HINT_JOYSTICK_LINUX_CLASSIC}) SDL_SetHint(hint, "0");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        Check(SDL_WasInit(0) == 0, "SDL state not fresh");
        Ok(SDL_Init(SDL_INIT_GAMEPAD), "private SDL init failed"); sdl = true;
        int count = -1; auto* initial = SDL_GetJoysticks(&count); SDL_free(initial);
        Check(count == 0, "unexpected external device; refusing input");
        auto make = library.Factory();
        module = static_cast<rex::IModule*>(make(rex::IModule::kInterface.name, rex::IModule::kInterface.version));
        auto* providers = static_cast<rex::IDriverModule*>(make(rex::IDriverModule::kInterface.name, rex::IDriverModule::kInterface.version));
        Check(module && providers, "real provider interfaces missing");
        Ok(module->Connect(factory), "provider Connect failed"); connected = true;
        Ok(module->Init(), "provider Init failed"); initialized = true;
        for (const auto& registration : providers->GetDrivers()) {
            if (registration.type != rex::DriverType::kInput || registration.name != "sdl3") continue;
            Check(!driver, "ambiguous SDL3 provider");
            loaded.provider = LoadedPath(reinterpret_cast<const void*>(registration.create));
            auto raw = registration.create(); driver.reset(static_cast<h::IInputDriver*>(raw.release()));
        }
        Check(bool(driver), "selected SDL3 driver missing");
        loaded.sdl = LoadedSDL(); loaded.base = LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger));
        Ok(rex::GetSettingsRegistry().SetText(rex::SettingLayer::kTitle, "hid.sdl.mappings_file", ""), "mapping isolation failed");
        Ok(driver->Initialize(dispatch), "driver Initialize failed"); running = true;
      } catch (...) { Cleanup(); throw; }
    }
    void Pump() { SDL_UpdateJoysticks(); SDL_PumpEvents(); dispatch.Drain(); }
    void Attach(const std::array<std::size_t, 4>& order) {
        for (auto p : order) { pads[p].Attach(p); ++created; }
        Pump(); // No SDK enumeration/read yet.
    }
    void Controls() {
        for (std::size_t p = 0; p < 4; ++p) {
            auto* joystick = pads[p].joystick;
            Ok(SDL_SetJoystickVirtualButton(joystick, static_cast<int>(p), true), "original button update failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, static_cast<Sint16>((p + 1) * 4096)), "original left X failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTY, -32768), "original left Y failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTX, static_cast<Sint16>(-static_cast<int>((p + 1) * 2048))), "original right X failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHTY, 32767), "original right Y failed");
            Ok(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, 32767), "original trigger failed");
        }
        Pump();
    }
    std::vector<h::PadDevice> Devices() {
        std::vector<h::PadDevice> devices;
        driver->EnumerateDevices(devices); dispatch.Drain(); driver->EnumerateDevices(devices);
        return devices;
    }
    h::PadState Read(std::size_t p) {
        const auto value = driver->GetDeviceState(ids[p]); Ok(value, "real SDK reading missing"); return *value;
    }
    unsigned Finish() {
        for (auto& pad : pads) pad.Detach(); Pump();
        Check(Devices().empty(), "virtual device survived detach");
        driver->Shutdown(); running = false; dispatch.Drain();
        Check(!driver->GetDeviceState(ids[0]) && driver->GetDeviceRevision() == 0 && dispatch.pending.empty(), "stopped driver/dispatcher not quiescent");
        driver.reset(); module->Shutdown(); initialized = false; module->Disconnect(); connected = false;
        unsigned cleaned = 0; for (const auto& pad : pads) cleaned += pad.cleaned;
        Check(cleaned == created, "owned virtual cleanup incomplete");
        SDL_Quit(); sdl = false; Check(SDL_WasInit(0) == 0, "SDL ownership leaked");
        return cleaned;
    }
    void Cleanup() {
        for (auto& pad : pads) {
            if (pad.instance) SDL_DetachVirtualJoystick(pad.instance);
            if (pad.joystick) SDL_CloseJoystick(pad.joystick);
            pad.instance = 0; pad.joystick = nullptr;
        }
        if (driver && running) { driver->Shutdown(); running = false; }
        dispatch.Drain(); driver.reset();
        if (module && initialized) { module->Shutdown(); initialized = false; }
        if (module && connected) { module->Disconnect(); connected = false; }
        if (sdl) { SDL_Quit(); sdl = false; }
    }
    ~Session() { Cleanup(); }
};

in::RawControls Convert(const h::PadState& state) {
    constexpr std::array<std::pair<u16, in::Control>, 15> mapping{{
        {h::kPadA,in::Control::south},{h::kPadB,in::Control::east},{h::kPadX,in::Control::west},{h::kPadY,in::Control::north},
        {h::kPadDPadUp,in::Control::up},{h::kPadDPadDown,in::Control::down},{h::kPadDPadLeft,in::Control::left},{h::kPadDPadRight,in::Control::right},
        {h::kPadStart,in::Control::start},{h::kPadBack,in::Control::back},{h::kPadLeftThumb,in::Control::left_stick},
        {h::kPadRightThumb,in::Control::right_stick},{h::kPadLeftShoulder,in::Control::left_shoulder},
        {h::kPadRightShoulder,in::Control::right_shoulder},{h::kPadGuide,in::Control::guide}}};
    in::RawControls raw{}; u16 known = 0;
    for (const auto& [sdk, host] : mapping) { known |= sdk; if ((state.buttons & sdk) != 0) raw.buttons |= in::bit(host); }
    Check((state.buttons & ~known) == 0, "unknown SDK controls");
    raw.sticks = {state.thumb_lx, state.thumb_ly, state.thumb_rx, state.thumb_ry};
    raw.triggers = {state.left_trigger, state.right_trigger}; return raw;
}
struct Routes {
    std::array<in::DeviceToken, 4> tokens{};
    std::array<in::Binding, 4> bindings{};
};
void Reserve(in::ControllerIngress& ingress) {
    for (std::size_t slot = 0; slot < 4; ++slot) Check(ingress.reserve(slot, owner_id[slot]) == in::Status::ok, "owner reservation failed");
}
Routes Bind(Session& session, in::ControllerIngress& ingress) {
    const auto devices = session.Devices(); Check(devices.size() == 4, "four real provider devices missing");
    Routes routes{}; std::array<bool, 4> seen{};
    for (const auto& device : devices) {
        Check(device.info.vendor == 0xffff && device.info.product >= 1 && device.info.product <= 4, "device not an original owned pad");
        const auto pad = static_cast<std::size_t>(device.info.product - 1);
        Check(!seen[pad] && device.id.value != 0, "duplicate original source"); seen[pad] = true;
        session.ids[pad] = device.id;
        auto found = ingress.discover(device.id.value); Check(found.result.ok(), "source discovery failed"); routes.tokens[pad] = found.token;
        auto joined = ingress.join(owner_slot[pad], owner_id[owner_slot[pad]], found.token);
        Check(joined.result.ok(), "explicit nonordinal join failed"); routes.bindings[pad] = joined.binding;
    }
    Check(ingress.active_sources() == 4, "source count differs"); return routes;
}
void VerifyState(const in::SlotState& state, std::size_t pad) {
    Check(state.owner == owner_id[owner_slot[pad]] && state.device != 0 && state.last_sequence != 0, "local owner route differs");
    Check(state.frame.buttons == (std::uint64_t{1} << pad) && state.frame.axes[1] == 1 && state.frame.axes[3] == -1 &&
          std::abs(state.frame.axes[0] - static_cast<float>(pad + 1) * 0.125003815f) < 0.000001f &&
          state.frame.axes[2] == -static_cast<float>(pad + 1) * 0.0625f && state.frame.triggers[0] == 0 && state.frame.triggers[1] == 1,
          "normalized input reached wrong owner");
}
in::RawControls Publish(Session& session, in::ControllerIngress& ingress, const Routes& routes) {
    in::RawControls first{};
    for (std::size_t pad = 0; pad < 4; ++pad) {
        Check(SDL_GetJoystickButton(session.pads[pad].joystick, static_cast<int>(pad)) &&
              SDL_GetJoystickAxis(session.pads[pad].joystick, SDL_GAMEPAD_AXIS_LEFTX) == static_cast<int>((pad + 1) * 4096), "SDL source not held");
        const auto sdk = session.Read(pad);
        Check(sdk.buttons == sdk_face[pad] && sdk.thumb_ly == 32767 && sdk.thumb_ry == -32768 &&
              sdk.left_trigger == 0 && sdk.right_trigger == 255, "actual SDK held state differs");
        const auto raw = Convert(sdk); if (pad == 0) first = raw;
        Check(ingress.publish(routes.bindings[pad], {routes.tokens[pad], 1, raw}).ok(), "observation publication failed");
        VerifyState(*ingress.state(owner_slot[pad]), pad);
    }
    return first;
}
void Changed(Session& session, in::ControllerIngress& ingress, const Routes& routes) {
    const auto before = ingress.slots();
    Ok(SDL_SetJoystickVirtualButton(session.pads[2].joystick, 2, false), "changed source update failed"); session.Pump();
    const auto raw = Convert(session.Read(2)); Check(raw.buttons == 0, "SDK changed button stale");
    Check(ingress.publish(routes.bindings[2], {routes.tokens[2], 2, raw}).ok(), "changed owner update failed");
    for (std::size_t pad = 0; pad < 4; ++pad) {
        if (pad == 2) Check(ingress.state(owner_slot[pad])->frame.buttons == 0, "changed owner unchanged");
        else Check(ingress.state(owner_slot[pad]) == before[owner_slot[pad]], "one source changed another owner");
    }
}
void ControlMap(Session& session, in::ControllerIngress& ingress, const Routes& routes) {
    struct Expected { SDL_GamepadButton button; u16 sdk; in::Control host; };
    constexpr std::array<Expected, 15> expected{{
        {SDL_GAMEPAD_BUTTON_SOUTH,h::kPadA,in::Control::south}, {SDL_GAMEPAD_BUTTON_EAST,h::kPadB,in::Control::east},
        {SDL_GAMEPAD_BUTTON_WEST,h::kPadX,in::Control::west}, {SDL_GAMEPAD_BUTTON_NORTH,h::kPadY,in::Control::north},
        {SDL_GAMEPAD_BUTTON_DPAD_UP,h::kPadDPadUp,in::Control::up}, {SDL_GAMEPAD_BUTTON_DPAD_DOWN,h::kPadDPadDown,in::Control::down},
        {SDL_GAMEPAD_BUTTON_DPAD_LEFT,h::kPadDPadLeft,in::Control::left}, {SDL_GAMEPAD_BUTTON_DPAD_RIGHT,h::kPadDPadRight,in::Control::right},
        {SDL_GAMEPAD_BUTTON_START,h::kPadStart,in::Control::start}, {SDL_GAMEPAD_BUTTON_BACK,h::kPadBack,in::Control::back},
        {SDL_GAMEPAD_BUTTON_LEFT_STICK,h::kPadLeftThumb,in::Control::left_stick}, {SDL_GAMEPAD_BUTTON_RIGHT_STICK,h::kPadRightThumb,in::Control::right_stick},
        {SDL_GAMEPAD_BUTTON_LEFT_SHOULDER,h::kPadLeftShoulder,in::Control::left_shoulder},
        {SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER,h::kPadRightShoulder,in::Control::right_shoulder},
        {SDL_GAMEPAD_BUTTON_GUIDE,h::kPadGuide,in::Control::guide}}};
    const auto before = ingress.slots(); auto* joystick = session.pads[0].joystick;
    Ok(SDL_SetJoystickVirtualButton(joystick, SDL_GAMEPAD_BUTTON_SOUTH, false), "release initial face failed"); session.Pump();
    std::uint64_t sequence = 1;
    for (const auto& item : expected) {
        Ok(SDL_SetJoystickVirtualButton(joystick, item.button, true), "original control press failed"); session.Pump();
        const auto sdk = session.Read(0); Check(sdk.buttons == item.sdk, "SDK logical control differs");
        Check(ingress.publish(routes.bindings[0], {routes.tokens[0], ++sequence, Convert(sdk)}).ok() &&
              ingress.state(owner_slot[0])->frame.buttons == in::bit(item.host), "named host control differs");
        Ok(SDL_SetJoystickVirtualButton(joystick, item.button, false), "original control release failed"); session.Pump();
        auto released = session.Read(0);
        if (item.button == SDL_GAMEPAD_BUTTON_GUIDE) {
            // Pinned SDL intentionally stretches a guide pulse to at least 250 ms.
            // Wait only for that source policy, with a deadline and no forced state.
            Check(!SDL_GetJoystickButton(joystick, item.button), "guide source still held");
            const auto started = SDL_GetTicks(); const bool pending = released.buttons != 0;
            while (released.buttons != 0 && SDL_GetTicks() - started < 1000) {
                Check(released.buttons == h::kPadGuide, "non-guide state blocked release");
                SDL_Delay(1); session.Pump(); released = session.Read(0);
            }
            std::cout << "MW3_INGRESS_POLICY:guide_pending=" << (pending ? 1 : 0)
                << " release_ms=" << SDL_GetTicks() - started << " source_released=1\n";
        }
        Check(released.buttons == 0, "SDK control stayed held");
        Check(ingress.publish(routes.bindings[0], {routes.tokens[0], ++sequence, Convert(released)}).ok() &&
              ingress.state(owner_slot[0])->frame.buttons == 0, "host control stayed held");
    }
    for (const auto& [axis, value] : std::array<std::pair<int, Sint16>, 6>{{
            {SDL_GAMEPAD_AXIS_LEFTX,-32768},{SDL_GAMEPAD_AXIS_LEFTY,32767},
            {SDL_GAMEPAD_AXIS_RIGHTX,32767},{SDL_GAMEPAD_AXIS_RIGHTY,-32768},
            {SDL_GAMEPAD_AXIS_LEFT_TRIGGER,0},{SDL_GAMEPAD_AXIS_RIGHT_TRIGGER,0}}}) {
        Ok(SDL_SetJoystickVirtualAxis(joystick, axis, value), "original opposite endpoint failed");
    }
    session.Pump(); const auto sdk = session.Read(0);
    Check(sdk.thumb_lx == -32768 && sdk.thumb_ly == -32768 && sdk.thumb_rx == 32767 && sdk.thumb_ry == 32767 &&
          sdk.left_trigger == 127 && sdk.right_trigger == 127, "SDK endpoint/midpoint quantization differs");
    Check(ingress.publish(routes.bindings[0], {routes.tokens[0], ++sequence, Convert(sdk)}).ok(), "opposite endpoint publication failed");
    const auto frame = ingress.state(owner_slot[0])->frame;
    Check(frame.axes == std::array<float,4>{-1,-1,1,1} &&
          std::abs(frame.triggers[0] - 0.49803922f) < 0.0000001f && frame.triggers[0] == frame.triggers[1], "host endpoint/midpoint differs");
    for (std::size_t pad : {1u,2u,3u}) Check(ingress.state(owner_slot[pad]) == before[owner_slot[pad]], "control mapping changed another owner");
}
void Reject(in::ControllerIngress& ingress, const Routes& routes, const in::RawControls& raw) {
    const auto before = ingress.slots();
    auto unknown = raw; unknown.buttons |= 1u << 31;
    Check(ingress.publish(routes.bindings[0], {routes.tokens[0], 2, unknown}).code == in::IngressCode::invalid_controls, "unknown controls accepted");
    Check(ingress.publish(routes.bindings[0], {routes.tokens[1], 2, raw}).code == in::IngressCode::mismatched_source, "wrong source accepted");
    auto stale = routes.tokens[0]; ++stale.session;
    Check(ingress.publish(routes.bindings[0], {stale, 2, raw}).code == in::IngressCode::stale_source, "foreign source accepted");
    Check(ingress.publish(routes.bindings[0], {routes.tokens[0], 1, raw}).routing_status == in::Status::out_of_order, "duplicate sequence accepted");
    auto wrong = routes.bindings[0]; ++wrong.owner;
    Check(ingress.publish(wrong, {routes.tokens[0], 2, raw}).routing_status == in::Status::stale_binding, "wrong owner accepted");
    const auto joined = ingress.join(owner_slot[0], owner_id[owner_slot[0]] + 1, routes.tokens[0]);
    Check(joined.result.routing_status == in::Status::wrong_owner && ingress.slots() == before, "rejection changed routes");
    Check(ingress.publish(routes.bindings[0], {routes.tokens[0], 2, raw}).ok(), "rejection consumed sequence");
}
void Hotplug(Session& session, in::ControllerIngress& ingress, const Routes& routes) {
    const auto before = ingress.slots(); const auto old_instance = session.pads[1].instance;
    session.pads[1].Detach(); session.Pump(); Check(session.Devices().size() == 3 && !session.driver->GetDeviceState(session.ids[1]), "SDK disconnect stale");
    Check(ingress.remove(routes.tokens[1]).ok(), "source removal failed");
    auto removed = ingress.state(owner_slot[1]);
    Check(removed->owner == owner_id[owner_slot[1]] && removed->device == 0 && removed->frame == in::Frame{}, "disconnect retained input or lost owner");
    session.pads[1].Attach(1); ++session.created; session.Pump();
    const auto devices = session.Devices(); Check(devices.size() == 4, "SDK reconnect missing");
    for (const auto& device : devices) if (device.info.vendor == 0xffff && device.info.product == 2) session.ids[1] = device.id;
    Check(session.ids[1].value != routes.tokens[1].device, "SDK reconnect reused raw ID unexpectedly");
    const auto found = ingress.discover(session.ids[1].value); Check(found.result.ok(), "reconnect discovery failed");
    const auto joined = ingress.join(owner_slot[1], owner_id[owner_slot[1]], found.token); Check(joined.result.ok(), "explicit reconnect join failed");
    SDL_Event late{}; late.type = SDL_EVENT_GAMEPAD_BUTTON_DOWN; late.gbutton.which = old_instance;
    late.gbutton.button = SDL_GAMEPAD_BUTTON_EAST; late.gbutton.down = true;
    Ok(SDL_PushEvent(&late), "late original SDK event injection failed"); session.Pump();
    Check(session.Read(1).buttons == 0, "late SDK event reached replacement");
    const auto next = ingress.slots();
    Check(ingress.publish(joined.binding, {routes.tokens[1], 5, {}}).code == in::IngressCode::stale_source &&
          ingress.remove(routes.tokens[1]).code == in::IngressCode::stale_source && ingress.slots() == next, "late ingress event stole replacement");
    session.Controls(); const auto raw = Convert(session.Read(1));
    Check(ingress.publish(joined.binding, {found.token, 1, raw}).ok(), "fresh reconnect publication failed");
    VerifyState(*ingress.state(owner_slot[1]), 1);
    for (std::size_t pad : {0u, 2u, 3u}) Check(ingress.state(owner_slot[pad]) == before[owner_slot[pad]], "hotplug changed another owner");
}
void Neutral(const in::ControllerIngress& ingress) {
    Check(ingress.active_sources() == 0, "stopped backend retained sources");
    for (std::size_t slot = 0; slot < 4; ++slot) {
        const auto state = ingress.state(slot);
        Check(state->owner == owner_id[slot] && state->device == 0 && state->frame == in::Frame{} && state->last_sequence == 0, "backend stop lost owner or retained input");
    }
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 4 && argc != 5) { std::cerr << "MW3_INGRESS_FAILURE:arguments required\n"; return 2; }
    const std::string_view name = argv[1], nonce = argv[2];
    const bool wrong = argc == 5 && std::string_view(argv[4]) == "--wrong-route";
    const std::array cases{"held", "orders", "hotplug", "restart", "rejections", "control-map"};
    if (std::find(cases.begin(), cases.end(), name) == cases.end() || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
        (argc == 5 && (!wrong || name != "held"))) { std::cerr << "MW3_INGRESS_FAILURE:invalid case or nonce\n"; return 2; }
    try {
        Loaded loaded; unsigned cycles = 0, created = 0, cleaned = 0;
        std::array<std::size_t, 4> order = name == "orders" ? std::array<std::size_t, 4>{0,1,2,3} : std::array<std::size_t, 4>{2,0,3,1};
        in::ControllerIngress persistent(10101); Reserve(persistent);
        Routes previous{}; std::array<h::PadDeviceID, 4> previous_ids{};
        bool wrong_comparison = false;
        do {
            in::ControllerIngress local(20000 + cycles); Reserve(local);
            auto& ingress = name == "restart" ? persistent : local;
            Session session(argv[3]);
            if (cycles == 0) { loaded = session.loaded; EmitLoaded(nonce, loaded); }
            else Check(session.loaded == loaded, "loaded library changed during process");
            session.Attach(order); session.Controls(); // Hold before first SDK discovery.
            const auto routes = Bind(session, ingress); const auto raw = Publish(session, ingress, routes);
            wrong_comparison = ingress.state(owner_slot[0])->frame.buttons == in::bit(in::Control::east);
            if (name == "restart" && cycles == 1) {
                const auto before = ingress.slots();
                for (std::size_t pad = 0; pad < 4; ++pad) {
                    Check(session.ids[pad] == previous_ids[pad] && routes.tokens[pad] != previous.tokens[pad], "actual SDK ID reuse/token distinction missing");
                    Check(ingress.publish(routes.bindings[pad], {previous.tokens[pad], 2, raw}).code == in::IngressCode::stale_source, "restart accepted old observation");
                    Check(ingress.publish(previous.bindings[pad], {routes.tokens[pad], 2, raw}).routing_status == in::Status::stale_binding, "restart accepted old ownership binding");
                }
                Check(ingress.slots() == before, "restart rejection changed live input");
            }
            if (name == "hotplug") Hotplug(session, ingress, routes);
            if (name == "rejections") Reject(ingress, routes, raw);
            if (name == "control-map") ControlMap(session, ingress, routes);
            if (name == "held" || name == "orders") Changed(session, ingress, routes);
            previous = routes; previous_ids = session.ids;
            Check(ingress.restart().ok(), "backend restart failed"); Neutral(ingress);
            created += session.created; cleaned += session.Finish(); ++cycles;
            if (name == "restart" && cycles < 2) continue;
            if (name != "orders" || !std::next_permutation(order.begin(), order.end())) break;
        } while (true);
        auto footer = [&](std::string_view prefix) {
            std::cout << prefix << "{\"schema\":1,\"case\":" << Quote(name) << ",\"nonce\":" << Quote(nonce)
                << ",\"cycles\":" << cycles << ",\"created\":" << created << ",\"cleaned\":" << cleaned
                << ",\"owners\":4,\"connected_after\":0,\"sources_after\":0,\"pending\":0,\"sdl_init_after\":" << SDL_WasInit(0)
                << ",\"checks\":" << checks << ",\"sdl_version\":" << SDL_GetVersion()
                << ",\"loaded\":{\"provider\":" << Quote(loaded.provider) << ",\"sdl\":" << Quote(loaded.sdl)
                << ",\"base\":" << Quote(loaded.base) << "}}\n" << std::flush;
        };
        if (wrong) { footer("MW3_INGRESS_REJECTED:"); Check(wrong_comparison, "deliberate wrong-route rejected"); }
        footer("MW3_INGRESS_COMPLETE:"); return 0;
    } catch (const std::exception& error) { std::cerr << "MW3_INGRESS_FAILURE:" << error.what() << '\n'; return 1; }
}
