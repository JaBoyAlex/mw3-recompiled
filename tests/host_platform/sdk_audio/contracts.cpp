// SPDX-License-Identifier: GPL-3.0-only
// Original PCM/ownership observations through actual approved SDK modules.
#include <SDL3/SDL.h>
#include <rex/app/app.h>
#include <rex/apu/audio_system.h>
#include <rex/platform/thread.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <semaphore>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#include <link.h>
#endif

namespace {
namespace apu = rex::apu;
using Clock = std::chrono::steady_clock;
using Frame = std::array<rex::f32, apu::kAudioFrameSamples>;
struct ContractApp : rex::app::App {
    ContractApp() : App("mw3_sdk_audio_061") {}
    rex::AppSysRequirements GetRequirements() const override {
        const char* mode = std::getenv("MW3_AUDIO_MODE");
        return {.audio = mode && std::string_view(mode) == "sdl"};
    }
};
void Require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
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
std::string ModulePath(const char* name) {
#ifdef _WIN32
    const auto module = GetModuleHandleW(std::filesystem::path(std::string(name) + ".dll").c_str());
    Require(module != nullptr, "expected-module-not-loaded");
    std::array<wchar_t, 32768> path{};
    const auto n = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
    Require(n && n < path.size(), "loaded-module-path-unavailable");
    return std::filesystem::path(path.data()).generic_string();
#else
    const auto file = "lib" + std::string(name) + (std::string_view(name) == "SDL3" ? ".so.0" : ".so");
    void* handle = dlopen(file.c_str(), RTLD_NOW | RTLD_NOLOAD);
    Require(handle != nullptr, "expected-module-not-loaded");
    link_map* map = nullptr;
    const bool ok = dlinfo(handle, RTLD_DI_LINKMAP, &map) == 0 && map && map->l_name;
    const auto result = ok ? std::filesystem::absolute(map->l_name).string() : "";
    dlclose(handle);
    Require(ok && !result.empty(), "loaded-module-path-unavailable");
    return result;
#endif
}
std::string VirtualModule(apu::IAudioSystem& audio) {
    const void* table = nullptr;
    const void* method = nullptr;
    std::memcpy(&table, static_cast<const void*>(&audio), sizeof(table));
    std::memcpy(&method, table, sizeof(method));
#ifdef _WIN32
    HMODULE module{};
    Require(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(method), &module) != 0, "audio-method-module-unavailable");
    std::array<wchar_t, 32768> path{};
    const auto n = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
    Require(n && n < path.size(), "audio-method-module-path-unavailable");
    return std::filesystem::path(path.data()).generic_string();
#else
    Dl_info info{};
    Require(dladdr(method, &info) && info.dli_fname, "audio-method-module-unavailable");
    return std::filesystem::absolute(info.dli_fname).string();
#endif
}
Frame PCM(unsigned tag = 0) {
    Frame frame{};
    for (std::size_t ch = 0; ch < apu::kAudioFrameChannels; ++ch)
        for (std::size_t sample = 0; sample < apu::kAudioChannelSamples; ++sample)
            frame[ch * apu::kAudioChannelSamples + sample] =
                static_cast<float>((tag + 1) * (ch + 1)) / 1024.0f * (sample % 2 ? 1.0f : -1.0f);
    return frame;
}
struct Signals {
    std::array<std::atomic<unsigned>, 64> counts{};
    std::counting_semaphore<65536> events{0};
    void Hit(unsigned index) { counts[index].fetch_add(1, std::memory_order_relaxed); events.release(); }
    unsigned Count(unsigned index) const { return counts[index].load(std::memory_order_relaxed); }
    void Wait(unsigned index, unsigned target) {
        const auto deadline = Clock::now() + std::chrono::seconds(3);
        while (Count(index) < target) {
            if (!events.try_acquire_until(deadline)) {
                Require(Count(index) >= target, "played-callback-deadline");
                break;
            }
        }
    }
    unsigned Total() const {
        unsigned result = 0;
        for (const auto& n : counts) result += n.load(std::memory_order_relaxed);
        return result;
    }
};
struct Observation {
    std::string name, status = "PASS", reason;
    unsigned checks = 0, opened = 0, accepted = 0, callbacks = 0, queue_peak = 0;
    unsigned old_id = 0, new_id = 0;
    bool stale_ok = false;
    std::uint64_t underruns = 0, elapsed_us = 0;
    std::vector<std::uint64_t> submit_ns;
    void Check(bool value, const char* message) { ++checks; Require(value, message); }
};
struct Streams {
    apu::IAudioSystem& audio;
    Signals& signals;
    Observation& out;
    std::vector<apu::AudioStreamID> owned;
    apu::AudioStreamID Open(unsigned signal) {
        auto result = audio.OpenStream([this, signal] { signals.Hit(signal); });
        out.Check(bool(result), "open-owned-stream-failed");
        owned.push_back(*result); ++out.opened;
        return *result;
    }
    void Close(apu::AudioStreamID id) {
        const auto it = std::find(owned.begin(), owned.end(), id);
        out.Check(it != owned.end(), "fixture-attempted-unowned-close");
        audio.CloseStream(id); owned.erase(it);
    }
    void CloseAll() { for (const auto id : owned) audio.CloseStream(id); owned.clear(); }
    ~Streams() { CloseAll(); }
    rex::Result<void> Submit(apu::AudioStreamID id, const Frame& frame) {
        out.Check(out.submit_ns.size() < 512, "submission-observation-budget");
        const auto started = Clock::now();
        auto result = audio.Submit(id, frame);
        out.submit_ns.push_back(static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - started).count()));
        if (result) ++out.accepted;
        const auto queued = audio.GetStats().queued_frames;
        out.queue_peak = std::max(out.queue_peak, queued);
        return result;
    }
};
void Capacity(apu::IAudioSystem& audio, Observation& o) {
    Signals signals; Streams streams{audio, signals, o, {}};
    std::array<apu::AudioStreamID, 8> ids{};
    for (unsigned i = 0; i < ids.size(); ++i) ids[i] = streams.Open(i);
    o.Check(audio.GetStats().open_streams == 8, "stream-capacity-accounting");
    auto excess = audio.OpenStream([] {});
    o.Check(!excess && excess.error().category == rex::ErrorCategory::kRuntime, "ninth-stream-not-rejected");
    const auto frame = PCM();
    for (const unsigned raw : {0U, 9U, 0xffffffffU}) {
        auto invalid = audio.Submit(static_cast<apu::AudioStreamID>(raw), frame);
        o.Check(!invalid && invalid.error().category == rex::ErrorCategory::kNotFound, "invalid-stream-not-rejected");
        audio.CloseStream(static_cast<apu::AudioStreamID>(raw));
        o.Check(audio.GetStats().open_streams == 8, "invalid-close-changed-owned-streams");
    }
    streams.CloseAll();
    o.callbacks = signals.Total();
    o.Check(o.callbacks == 0, "unsubmitted-stream-played-callback");
}
void Identity(apu::IAudioSystem& audio, Observation& o) {
    Signals signals; Streams streams{audio, signals, o, {}};
    const auto other = streams.Open(0);
    const auto old = streams.Open(1);
    const auto frame = PCM(1);
    o.Check(bool(streams.Submit(old, frame)), "identity-first-submit");
    signals.Wait(1, 1); streams.Close(old);
    auto closed = audio.Submit(old, frame);
    o.Check(!closed && closed.error().category == rex::ErrorCategory::kNotFound, "closed-id-not-rejected");
    const auto replacement = streams.Open(2);
    o.old_id = static_cast<unsigned>(old); o.new_id = static_cast<unsigned>(replacement);
    auto stale = streams.Submit(old, frame);
    o.stale_ok = bool(stale);
    if (stale) signals.Wait(2, 1);
    else o.Check(stale.error().category == rex::ErrorCategory::kNotFound, "stale-rejection-category");
    o.Check(signals.Count(0) == 0 && signals.Count(1) == 1, "replacement-changed-other-owner-callbacks");
    o.Check(signals.Count(2) == (stale ? 1U : 0U), "stale-submit-callback-observation");
    streams.Close(replacement); streams.Close(other);
    o.callbacks = signals.Total();
    // This is an MW3 ownership requirement, not an invented SDK generation API.
    // Retain a raw-slot alias as a FAIL and leave any adapter/SDK repair separate.
    o.Check(!o.stale_ok, "stale-stream-id-retargeted-replacement");
}
void Queue(apu::IAudioSystem& audio, Observation& o) {
    Signals signals; Streams streams{audio, signals, o, {}};
    const auto a = streams.Open(0), b = streams.Open(1);
    const auto frame = PCM(2);
    const auto before = audio.GetStats().underruns;
    bool full = false;
    for (unsigned i = 0; i < 256; ++i) {
        auto result = streams.Submit(a, frame);
        if (!result) {
            o.Check(result.error().category == rex::ErrorCategory::kRuntime, "queue-overflow-wrong-category");
            full = true; break;
        }
    }
    o.Check(full && o.accepted >= 4 && o.queue_peak <= 4, "queue-limit-not-observed");
    const unsigned accepted_a = o.accepted;
    signals.Wait(0, accepted_a);
    o.Check(signals.Count(1) == 0, "other-empty-stream-played-callback");
    o.Check(bool(streams.Submit(b, PCM(3))), "independent-stream-submit");
    signals.Wait(1, 1);
    o.Check(signals.Count(0) == accepted_a && signals.Count(1) == 1, "cross-stream-callback-routing");
    o.underruns = audio.GetStats().underruns - before;
    o.Check(o.underruns > 0 && audio.GetStats().queued_frames == 0, "underrun-or-drain-not-observed");
    streams.CloseAll(); o.callbacks = signals.Total();
    o.Check(o.callbacks == o.accepted, "played-count-does-not-match-submissions");
}
void Lifecycle(apu::IAudioSystem& audio, Observation& o) {
    Signals signals; Streams streams{audio, signals, o, {}};
    const auto frame = PCM(4);
    for (unsigned i = 0; i < 32; ++i) {
        const auto id = streams.Open(2 * i);
        for (unsigned n = 0; n < 4; ++n) o.Check(bool(streams.Submit(id, frame)), "lifecycle-submit");
        streams.Close(id);
        const auto closed_count = signals.Count(2 * i);
        o.Check(audio.GetStats().queued_frames == 0, "close-did-not-discard-queue");
        const auto observer = streams.Open(2 * i + 1);
        o.Check(bool(streams.Submit(observer, frame)), "lifecycle-observer-submit");
        signals.Wait(2 * i + 1, 1); streams.Close(observer);
        o.Check(signals.Count(2 * i) == closed_count, "callback-arrived-after-close");
        o.Check(audio.GetStats().open_streams == 0, "lifecycle-stream-leak");
    }
    o.callbacks = signals.Total();
    o.Check(o.opened == 64 && o.accepted == 160 && o.callbacks >= 32 && o.callbacks <= 160,
            "lifecycle-accounting");
}
void Print(const Observation& o) {
    std::cout << "{\"name\":" << Quote(o.name) << ",\"status\":" << Quote(o.status) << ",\"reason\":" << Quote(o.reason)
        << ",\"checks\":" << o.checks << ",\"opened\":" << o.opened << ",\"accepted\":" << o.accepted
        << ",\"callbacks\":" << o.callbacks << ",\"queue_peak\":" << o.queue_peak
        << ",\"old_id\":" << o.old_id << ",\"new_id\":" << o.new_id << ",\"stale_ok\":" << (o.stale_ok ? "true" : "false")
        << ",\"underruns\":" << o.underruns << ",\"elapsed_us\":" << o.elapsed_us << ",\"submit_ns\":[";
    for (std::size_t i = 0; i < o.submit_ns.size(); ++i) { if (i) std::cout << ','; std::cout << o.submit_ns[i]; }
    std::cout << "]}";
}
std::vector<std::string> Cases(const std::string& text) {
    Require(!text.empty() && text.size() <= 256, "invalid-case-list");
    std::vector<std::string> out;
    std::size_t begin = 0;
    while (begin < text.size()) {
        const auto end = text.find(',', begin);
        const auto name = text.substr(begin, end == std::string::npos ? end : end - begin);
        Require(name == "capacity" || name == "identity" || name == "queue" || name == "lifecycle", "unknown-case");
        Require(out.size() < 16, "case-list-budget"); out.push_back(name);
        if (end == std::string::npos) return out;
        begin = end + 1; Require(begin < text.size(), "trailing-case-separator");
    }
    return out;
}
int Run(ContractApp& app, const rex::CLIArgList& args) {
    const char* case_value = std::getenv("MW3_AUDIO_CASES");
    const char* mode_value = std::getenv("MW3_AUDIO_MODE");
    const char* nonce_value = std::getenv("MW3_AUDIO_NONCE");
    const char* tree_value = std::getenv("MW3_AUDIO_TREE");
    if (!case_value || !mode_value || !nonce_value || !tree_value) return 2;
    const std::string mode(mode_value), nonce(nonce_value), requested(case_value);
    const bool bad_backend = requested == "invalid-driver";
    const bool incomplete = requested == "incomplete";
    const bool wrong = std::getenv("MW3_AUDIO_WRONG") != nullptr;
    if ((mode != "timer" && mode != "sdl") || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); })) return 2;
    const auto before = rex::platform::detail::GetThreadCount();
    try {
        const auto cases = bad_backend || incomplete ? std::vector<std::string>{} : Cases(requested);
        const auto owner = std::filesystem::path(tree_value) / ".owner";
        Require(std::filesystem::file_size(owner) < 100, "invalid-private-owner-size");
        std::ifstream file(owner, std::ios::binary);
        const std::string marker{std::istreambuf_iterator<char>(file), {}};
        Require(marker == "mw3-sdk-audio-v1\n" + nonce + "\n", "invalid-private-owner-marker");
        auto initialized = app.Init(args);
        if (bad_backend) {
            Require(mode == "sdl" && !initialized && initialized.error().category == rex::ErrorCategory::kModule,
                    "invalid-audio-backend-not-rejected");
            const auto message = initialized.error().message;
            Require(message.find("module 'rexapu' failed to init, no audio driver is available") != std::string::npos,
                    "invalid-audio-backend-unexpected-rejection");
            const auto shutdown = app.Shutdown();
            Require(SDL_WasInit(SDL_INIT_AUDIO) == 0 && rex::platform::detail::GetThreadCount() == before,
                    "invalid-backend-cleanup-failed");
            std::cout << "MW3_AUDIO_BACKEND_REJECTED:{\"nonce\":" << Quote(nonce) << ",\"message\":" << Quote(message)
                      << ",\"category\":" << static_cast<unsigned>(initialized.error().category)
                      << ",\"shutdown\":" << shutdown << ",\"threads_before\":" << before
                      << ",\"threads_after\":" << rex::platform::detail::GetThreadCount()
                      << ",\"sdl_audio_after\":" << SDL_WasInit(SDL_INIT_AUDIO) << "}\n";
            return 44;
        }
        Require(bool(initialized), "app-init-failed");
        auto& audio = app.GetAudio();
        Require(audio.GetSettings().max_queued_frames.Get() == 4, "unexpected-queue-configuration");
        Require(audio.GetSettings().driver.Get() == (mode == "sdl" ? "sdl3" : "none"), "unexpected-sdk-audio-driver");
        Require(SDL_GetVersion() == 3004014, "unexpected-SDL-version");
        const char* active = SDL_GetCurrentAudioDriver();
        Require(mode == "sdl" ? active && std::string_view(active) == "dummy" : active == nullptr,
                "unexpected-active-SDL-backend");
        const auto backend = mode == "sdl" ? "dummy" : "none";
        const auto channels = audio.GetOutputChannels();
        // In this pinned dummy profile a successful open reports six; two can
        // also describe the SDK's timer fallback and must not certify a device.
        Require(channels == (mode == "sdl" ? 6U : 2U), "unexpected-output-channel-count-or-fallback");
        std::cout << "MW3_AUDIO_LIBRARIES:{\"nonce\":" << Quote(nonce) << ",\"mode\":" << Quote(mode)
            << ",\"backend\":" << Quote(backend) << ",\"loaded\":{\"audio\":" << Quote(VirtualModule(audio))
            << ",\"app\":" << Quote(ModulePath("rexapp")) << ",\"base\":" << Quote(ModulePath("rexbase"))
            << ",\"sdl\":" << Quote(ModulePath("SDL3")) << ",\"provider\":"
            << (mode == "sdl" ? Quote(ModulePath("rexapu-sdl3")) : "null") << "}}\n" << std::flush;
        if (incomplete) {
            // Test a missing completion record, not CRT/DLL detach with active
            // SDK threads. Crashes/timeouts have separate fail-closed guards.
            Require(app.Shutdown() == 0 && rex::platform::detail::GetThreadCount() == before &&
                    SDL_WasInit(SDL_INIT_AUDIO) == 0, "incomplete-control-cleanup-failed");
            std::cout << "MW3_AUDIO_INCOMPLETE:" << nonce << '\n' << std::flush;
            return 43;
        }
        std::vector<Observation> observations;
        bool failed = false;
        for (const auto& name : cases) {
            Observation o; o.name = name;
            const auto started = Clock::now();
            try {
                if (name == "capacity") Capacity(audio, o);
                else if (name == "identity") Identity(audio, o);
                else if (name == "queue") Queue(audio, o);
                else Lifecycle(audio, o);
                o.Check(!wrong, "deliberate-wrong-result");
            } catch (const std::exception& error) { o.status = "FAIL"; o.reason = error.what(); failed = true; }
            o.elapsed_us = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - started).count());
            Require(audio.GetStats().open_streams == 0 && audio.GetStats().queued_frames == 0, "case-resources-not-recovered");
            observations.push_back(std::move(o));
        }
        const auto shutdown = app.Shutdown();
        const auto after = rex::platform::detail::GetThreadCount();
        Require(shutdown == 0 && before == after && SDL_WasInit(SDL_INIT_AUDIO) == 0, "app-resources-not-recovered");
        std::cout << "MW3_AUDIO_COMPLETE:{\"schema\":1,\"nonce\":" << Quote(nonce) << ",\"mode\":" << Quote(mode)
            << ",\"backend\":" << Quote(backend) << ",\"channels\":" << channels
            << ",\"threads_before\":" << before << ",\"threads_after\":" << after
            << ",\"open_after\":0,\"queued_after\":0,\"sdl_audio_after\":0,\"cases\":[";
        for (std::size_t i = 0; i < observations.size(); ++i) { if (i) std::cout << ','; Print(observations[i]); }
        std::cout << "]}\n";
        return failed ? 42 : 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_AUDIO_FATAL:" << error.what() << '\n';
        app.Shutdown(); return 2;
    }
}
} // namespace
REX_CONSOLE_APP_MAIN(ContractApp, Run)
