// SPDX-License-Identifier: GPL-3.0-only
// Stage the unchanged MW3-084 contracts alongside this file for fixture reuse.
#define main mw3_raw_input_baseline_main
#include "baseline-contracts.cpp"
#undef main

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    const std::string_view mode = argv[1], nonce = argv[2];
    if ((mode != "pending-live" && mode != "pending-removed") || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) {
            return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
        })) return 2;
    try {
        // Callback storage outlives both the provider and every queued reference.
        VirtualPad queued;
        Fixture fixture(argv[3]);
        struct DetachOwned {
            VirtualPad& pad;
            ~DetachOwned() {
                if (pad.instance) SDL_DetachVirtualJoystick(pad.instance);
                if (pad.joystick) SDL_CloseJoystick(pad.joystick);
                pad.instance = 0; pad.joystick = nullptr;
            }
        } detach{queued};
        const auto provider = fixture.provider_path, sdl = LoadedSDL();
        const auto base = LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger));
        queued.Attach(4); fixture.Pump();
        // Do not enumerate/read: this add must remain queued in the provider.
        if (mode == "pending-removed") { queued.Detach(); fixture.Pump(); }
        fixture.driver->Shutdown(); fixture.running = false;
        fixture.dispatcher.Drain();
        queued.Detach();
        Check(queued.cleaned == 1, "undiscovered gamepad handle survived shutdown");
        const auto cleaned = fixture.Finish();
        std::cout << "MW3_SNAPSHOT_COMPLETE:{\"schema\":1,\"case\":" << Quote(mode)
            << ",\"nonce\":" << Quote(nonce) << ",\"created\":5,\"cleaned\":" << cleaned + queued.cleaned
            << ",\"pending\":0,\"sdl_init_after\":0,\"checks\":" << checks
            << ",\"loaded\":{\"provider\":" << Quote(provider) << ",\"sdl\":" << Quote(sdl)
            << ",\"base\":" << Quote(base) << "}}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_SNAPSHOT_FAILURE:" << error.what() << '\n'; return 1;
    }
}
