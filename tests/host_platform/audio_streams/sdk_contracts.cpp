// SPDX-License-Identifier: GPL-3.0-only
// Original diagnostic bridge only. No SDK implementation or guest service.
#include "streams.hpp"
#include <SDL3/SDL.h>
#include <rex/app/app.h>
#include <rex/apu/audio_system.h>
#include <rex/platform/thread.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <semaphore>
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
namespace a = mw3::audio;
namespace apu = rex::apu;
using Clock = std::chrono::steady_clock;
using PCM = std::array<float, a::frame_samples>;
void Require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
struct App : rex::app::App {
    App() : rex::app::App("mw3_audio_lifetimes_062") {}
    rex::AppSysRequirements GetRequirements() const override {
        const char* mode = std::getenv("MW3_AUDIO_MODE");
        return {.audio = mode && std::string_view(mode) == "sdl"};
    }
};
std::string Quote(std::string_view text) {
    std::string out = "\"";
    for (const unsigned char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) {
            out += "\\u00"; out += "0123456789abcdef"[c >> 4]; out += "0123456789abcdef"[c & 15];
        } else out += static_cast<char>(c);
    }
    return out + '"';
}
std::string Module(const char* name) {
#ifdef _WIN32
    const auto h = GetModuleHandleW(std::filesystem::path(std::string(name) + ".dll").c_str());
    Require(h != nullptr, "module-not-loaded");
    std::array<wchar_t, 32768> path{};
    const auto size = GetModuleFileNameW(h, path.data(), static_cast<DWORD>(path.size()));
    Require(size && size < path.size(), "module-path-truncated");
    return std::filesystem::path(path.data()).generic_string();
#else
    const auto file = "lib" + std::string(name) + (std::string_view(name) == "SDL3" ? ".so.0" : ".so");
    void* h = dlopen(file.c_str(), RTLD_NOW | RTLD_NOLOAD);
    Require(h != nullptr, "module-not-loaded");
    link_map* map = nullptr;
    const bool ok = dlinfo(h, RTLD_DI_LINKMAP, &map) == 0 && map && map->l_name;
    const auto path = ok ? std::filesystem::absolute(map->l_name).string() : "";
    dlclose(h); Require(!path.empty(), "module-path-unavailable"); return path;
#endif
}
std::string AudioModule(apu::IAudioSystem& audio) {
    const void* table = nullptr; const void* method = nullptr;
    std::memcpy(&table, static_cast<const void*>(&audio), sizeof(table));
    std::memcpy(&method, table, sizeof(method));
#ifdef _WIN32
    HMODULE h{};
    Require(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(method), &h) != 0, "audio-method-module-unavailable");
    std::array<wchar_t, 32768> path{};
    const auto size = GetModuleFileNameW(h, path.data(), static_cast<DWORD>(path.size()));
    Require(size && size < path.size(), "audio-method-path-unavailable");
    return std::filesystem::path(path.data()).generic_string();
#else
    Dl_info info{};
    Require(dladdr(method, &info) && info.dli_fname, "audio-method-module-unavailable");
    return std::filesystem::absolute(info.dli_fname).string();
#endif
}
struct Signals {
    std::array<std::atomic<unsigned>, 3> raw{};
    std::counting_semaphore<65536> pulse{0};
    template<class Predicate> void Until(Predicate&& predicate) {
        const auto deadline = Clock::now() + std::chrono::seconds(3);
        while (!predicate()) {
            if (!pulse.try_acquire_until(deadline)) { Require(predicate(), "callback-progress-deadline"); break; }
        }
    }
};
struct Bridge final : a::Backend {
    apu::IAudioSystem& audio;
    Signals& signal;
    std::array<a::RawId, 8> owned{};
    unsigned opens = 0, submits = 0, closes = 0, bad_closes = 0;
    a::RawId last_open = 0;
    rex::ErrorCategory last_error = rex::ErrorCategory::kNoError;
    Bridge(apu::IAudioSystem& source, Signals& signals) : audio(source), signal(signals) {}
    a::RawId open(a::Played cb) override {
        auto result = audio.OpenStream([played = std::move(cb), this] { played(); signal.pulse.release(); });
        if (!result) throw std::runtime_error("SDK-open:" + result.error().message);
        const auto free = std::find(owned.begin(), owned.end(), 0U);
        Require(free != owned.end(), "bridge-ownership-budget");
        *free = static_cast<a::RawId>(*result); last_open = *free; ++opens;
        return *free;
    }
    void submit(a::RawId raw, a::Frame frame) override {
        ++submits; last_error = rex::ErrorCategory::kNoError;
        auto result = audio.Submit(static_cast<apu::AudioStreamID>(raw), frame);
        if (!result) { last_error = result.error().category; throw std::runtime_error("SDK-submit:" + result.error().message); }
    }
    void close(a::RawId raw) noexcept override {
        const auto found = std::find(owned.begin(), owned.end(), raw);
        if (!raw || found == owned.end()) { ++bad_closes; return; }
        audio.CloseStream(static_cast<apu::AudioStreamID>(raw)); *found = 0; ++closes;
    }
    void CloseAll() noexcept { for (const auto raw : owned) if (raw) close(raw); }
    ~Bridge() { CloseAll(); }
};
PCM Frame(unsigned tag = 1) {
    PCM frame{};
    for (std::size_t channel = 0; channel < 6; ++channel)
        for (std::size_t i = 0; i < 256; ++i)
            frame[channel * 256 + i] = static_cast<float>((channel + 1) * tag) / 1024.0f * (i % 2 ? 1.0f : -1.0f);
    return frame;
}
struct Observation {
    std::string name, status = "PASS", reason;
    unsigned checks = 0, opens = 0, closes = 0, sdk_submits = 0, valid_submits = 0, credits = 0;
    unsigned stale_blocks = 0, owner_blocks = 0, instance_blocks = 0, frame_blocks = 0, queue_refusals = 0;
    bool raw_checked = false, raw_stale_accepted = false;
    a::RawId raw_old = 0, raw_new = 0;
    std::uint64_t elapsed_us = 0;
    std::vector<std::uint64_t> accepted_ns, rejected_ns, raw_ns;
    void Check(bool value, const char* reason_text) { ++checks; Require(value, reason_text); }
};
std::uint64_t Duration(Clock::time_point start) {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count());
}
void Submit(a::Gate& gate, const a::Token& token, a::OwnerId owner, const PCM& frame, Observation& o) {
    const auto started = Clock::now(); gate.submit(token, owner, frame);
    o.accepted_ns.push_back(Duration(started)); ++o.valid_submits;
}
template<class F> void Block(Bridge& b, Observation& o, a::Code expected, unsigned& count, F&& action) {
    const auto calls = b.submits;
    const auto started = Clock::now();
    bool rejected = false;
    try { action(); }
    catch (const a::Error& error) { o.Check(error.code() == expected, "wrong-gate-rejection-category"); rejected = true; }
    o.rejected_ns.push_back(Duration(started));
    o.Check(rejected && b.submits == calls, "rejected-command-reached-SDK"); ++count;
}
void Played(a::Gate& gate, const a::Token& token, a::OwnerId owner, unsigned expected, Bridge& b, Observation& o) {
    std::uint64_t seen = 0;
    b.signal.Until([&] { seen += gate.take_played(token, owner); return seen >= expected; });
    o.Check(seen == expected, "gate-credit-count"); o.credits += expected;
}
void Reuse(Bridge& b, Observation& o) {
    const auto frame = Frame();
    const auto other = b.open([&] { ++b.signal.raw[0]; });
    const auto old = b.open([&] { ++b.signal.raw[1]; });
    auto start = Clock::now(); b.submit(old, frame); o.raw_ns.push_back(Duration(start));
    b.signal.Until([&] { return b.signal.raw[1] == 1; }); b.close(old);
    const auto replacement = b.open([&] { ++b.signal.raw[2]; });
    o.raw_checked = true; o.raw_old = old; o.raw_new = replacement;
    start = Clock::now(); b.submit(old, frame); o.raw_ns.push_back(Duration(start)); o.raw_stale_accepted = true;
    b.signal.Until([&] { return b.signal.raw[2] == 1; });
    o.Check(old == replacement && old == 2 && b.signal.raw[0] == 0 && b.signal.raw[1] == 1,
            "raw-baseline-not-reproduced");
    b.close(replacement); b.close(other);
    a::Gate gate(b);
    const auto unchanged = gate.open(101), closed = gate.open(202);
    Submit(gate, closed, 202, frame, o); Played(gate, closed, 202, 1, b, o);
    gate.close(closed, 202);
    const auto current = gate.open(202);
    o.Check(b.last_open == old, "protected-probe-did-not-reuse-raw-ID");
    Block(b, o, a::Code::stale_token, o.stale_blocks, [&] { gate.submit(closed, 202, frame); });
    o.Check(gate.take_played(current, 202) == 0 && gate.take_played(unchanged, 101) == 0, "stale-command-credited-owner");
    Submit(gate, current, 202, frame, o); Played(gate, current, 202, 1, b, o);
    Submit(gate, unchanged, 101, frame, o); Played(gate, unchanged, 101, 1, b, o);
    gate.shutdown(); o.Check(gate.active_streams() == 0, "gate-shutdown-leak");
}
void Owners(Bridge& b, Observation& o) {
    a::Gate gate(b), other(b); const auto frame = Frame(2);
    const auto x = gate.open(11), y = gate.open(22), z = other.open(33);
    Block(b, o, a::Code::wrong_owner, o.owner_blocks, [&] { gate.submit(x, 22, frame); });
    Block(b, o, a::Code::foreign_token, o.instance_blocks, [&] { other.submit(x, 11, frame); });
    gate.close_owner(11);
    Block(b, o, a::Code::stale_token, o.stale_blocks, [&] { gate.submit(x, 11, frame); });
    Submit(gate, y, 22, frame, o); Played(gate, y, 22, 1, b, o);
    Submit(other, z, 33, frame, o); Played(other, z, 33, 1, b, o);
    o.Check(gate.active_streams() == 1 && other.active_streams() == 1, "owner-close-crossed-instances");
    gate.shutdown(); other.shutdown();
}
void Queue(Bridge& b, Observation& o) {
    a::Gate gate(b); const auto frame = Frame(3);
    const auto x = gate.open(1), y = gate.open(2);
    Block(b, o, a::Code::invalid_frame, o.frame_blocks, [&] { gate.submit(x, 1, std::span<const float>{}); });
    Block(b, o, a::Code::invalid_frame, o.frame_blocks, [&] { gate.submit(x, 1, std::span(frame).first(a::frame_samples - 1)); });
    bool full = false;
    for (unsigned n = 0; n < 256; ++n) {
        try { Submit(gate, x, 1, frame, o); }
        catch (const std::runtime_error& error) {
            o.Check(b.last_error == rex::ErrorCategory::kRuntime &&
                std::string(error.what()) == "SDK-submit:audio stream queue is full", "wrong-backend-refusal");
            full = true; ++o.queue_refusals; break;
        }
    }
    o.Check(full && o.valid_submits >= 4 && b.audio.GetStats().queued_frames <= 4, "SDK-queue-limit-not-observed");
    Played(gate, x, 1, o.valid_submits, b, o);
    o.Check(gate.take_played(y, 2) == 0, "queue-failure-changed-other-owner");
    Submit(gate, x, 1, frame, o); Played(gate, x, 1, 1, b, o);
    Submit(gate, y, 2, frame, o); Played(gate, y, 2, 1, b, o);
    gate.shutdown();
}
void Lifecycle(Bridge& b, Observation& o) {
    a::Gate gate(b); const auto frame = Frame(4);
    for (unsigned cycle = 0; cycle < 32; ++cycle) {
        const auto closed = gate.open(1);
        for (unsigned i = 0; i < 4; ++i) Submit(gate, closed, 1, frame, o);
        gate.close(closed, 1);
        const auto current = gate.open(2);
        Block(b, o, a::Code::stale_token, o.stale_blocks, [&] { gate.submit(closed, 1, frame); });
        o.Check(gate.take_played(current, 2) == 0, "replacement-inherited-completion");
        Submit(gate, current, 2, frame, o); Played(gate, current, 2, 1, b, o);
        gate.close(current, 2);
        o.Check(gate.active_streams() == 0 && b.audio.GetStats().queued_frames == 0, "lifecycle-stream-leak");
    }
    gate.shutdown();
    o.Check(o.valid_submits == 160 && o.credits == 32 && o.stale_blocks == 32, "lifecycle-accounting");
}
void Times(const std::vector<std::uint64_t>& values) {
    std::cout << '[';
    for (std::size_t i = 0; i < values.size(); ++i) { if (i) std::cout << ','; std::cout << values[i]; }
    std::cout << ']';
}
void Print(const Observation& o) {
    std::cout << "{\"name\":" << Quote(o.name) << ",\"status\":" << Quote(o.status) << ",\"reason\":" << Quote(o.reason)
        << ",\"checks\":" << o.checks << ",\"opens\":" << o.opens << ",\"closes\":" << o.closes
        << ",\"sdk_submits\":" << o.sdk_submits << ",\"valid_submits\":" << o.valid_submits << ",\"credits\":" << o.credits
        << ",\"stale_blocks\":" << o.stale_blocks << ",\"owner_blocks\":" << o.owner_blocks
        << ",\"instance_blocks\":" << o.instance_blocks << ",\"frame_blocks\":" << o.frame_blocks
        << ",\"queue_refusals\":" << o.queue_refusals << ",\"raw_checked\":" << (o.raw_checked ? "true" : "false")
        << ",\"raw_stale_accepted\":" << (o.raw_stale_accepted ? "true" : "false")
        << ",\"raw_old\":" << o.raw_old << ",\"raw_new\":" << o.raw_new << ",\"elapsed_us\":" << o.elapsed_us
        << ",\"accepted_ns\":"; Times(o.accepted_ns);
    std::cout << ",\"rejected_ns\":"; Times(o.rejected_ns);
    std::cout << ",\"raw_ns\":"; Times(o.raw_ns); std::cout << '}';
}
std::vector<std::string> Cases(const std::string& text) {
    Require(!text.empty() && text.size() <= 256, "invalid-case-list");
    std::vector<std::string> out;
    std::size_t begin = 0;
    while (begin < text.size()) {
        const auto end = text.find(',', begin);
        const auto name = text.substr(begin, end == std::string::npos ? end : end - begin);
        Require(name == "reuse" || name == "owners" || name == "queue" || name == "lifecycle", "unknown-case");
        Require(out.size() < 16, "case-list-budget"); out.push_back(name);
        if (end == std::string::npos) return out;
        begin = end + 1; Require(begin < text.size(), "trailing-case-separator");
    }
    return out;
}
int Run(App& app, const rex::CLIArgList& args) {
    const char* cases_value = std::getenv("MW3_AUDIO_CASES");
    const char* mode_value = std::getenv("MW3_AUDIO_MODE");
    const char* nonce_value = std::getenv("MW3_AUDIO_NONCE");
    const char* tree_value = std::getenv("MW3_AUDIO_TREE");
    if (!cases_value || !mode_value || !nonce_value || !tree_value) return 2;
    const std::string requested(cases_value), mode(mode_value), nonce(nonce_value);
    if ((mode != "timer" && mode != "sdl") || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); })) return 2;
    const bool incomplete = requested == "incomplete";
    const bool wrong = std::getenv("MW3_AUDIO_WRONG") != nullptr;
    const auto before = rex::platform::detail::GetThreadCount();
    try {
        const auto selected = incomplete ? std::vector<std::string>{} : Cases(requested);
        const auto owner = std::filesystem::path(tree_value) / ".owner";
        Require(std::filesystem::file_size(owner) < 100, "invalid-owner-marker-size");
        std::ifstream file(owner, std::ios::binary);
        const std::string marker{std::istreambuf_iterator<char>(file), {}};
        Require(marker == "mw3-audio-streams-v1\n" + nonce + "\n", "invalid-owner-marker");
        Require(bool(app.Init(args)), "app-init-failed");
        auto& audio = app.GetAudio();
        Require(audio.GetSettings().driver.Get() == (mode == "sdl" ? "sdl3" : "none") &&
                audio.GetSettings().max_queued_frames.Get() == 4, "unexpected-audio-configuration");
        const char* actual = SDL_GetCurrentAudioDriver();
        Require(mode == "sdl" ? actual && std::string_view(actual) == "dummy" : actual == nullptr, "unexpected-backend");
        const auto channels = audio.GetOutputChannels();
        Require(channels == (mode == "sdl" ? 6U : 2U) && SDL_GetVersion() == 3004014, "device-fallback-or-wrong-SDL");
        const auto backend = mode == "sdl" ? "dummy" : "none";
        std::cout << "MW3_AUDIO_LIBRARIES:{\"nonce\":" << Quote(nonce) << ",\"mode\":" << Quote(mode)
            << ",\"backend\":" << Quote(backend) << ",\"loaded\":{\"audio\":" << Quote(AudioModule(audio))
            << ",\"app\":" << Quote(Module("rexapp")) << ",\"base\":" << Quote(Module("rexbase"))
            << ",\"sdl\":" << Quote(Module("SDL3")) << ",\"provider\":"
            << (mode == "sdl" ? Quote(Module("rexapu-sdl3")) : "null") << "}}\n" << std::flush;
        if (incomplete) {
            Require(app.Shutdown() == 0 && rex::platform::detail::GetThreadCount() == before && SDL_WasInit(SDL_INIT_AUDIO) == 0,
                    "incomplete-control-cleanup");
            std::cout << "MW3_AUDIO_GATE_INCOMPLETE:" << nonce << '\n'; return 43;
        }
        std::vector<Observation> observations;
        bool failed = false;
        for (const auto& name : selected) {
            Observation o; o.name = name;
            Signals signal; Bridge b(audio, signal);
            const auto started = Clock::now();
            try {
                if (name == "reuse") Reuse(b, o);
                else if (name == "owners") Owners(b, o);
                else if (name == "queue") Queue(b, o);
                else Lifecycle(b, o);
                o.Check(!wrong, "deliberate-wrong-result");
            } catch (const std::exception& error) { failed = true; o.status = "FAIL"; o.reason = error.what(); }
            b.CloseAll();
            o.opens = b.opens; o.closes = b.closes; o.sdk_submits = b.submits;
            o.elapsed_us = Duration(started) / 1000;
            Require(b.bad_closes == 0 && b.opens == b.closes && audio.GetStats().open_streams == 0 &&
                    audio.GetStats().queued_frames == 0, "case-resources-not-recovered");
            observations.push_back(std::move(o));
        }
        const auto shutdown = app.Shutdown();
        const auto after = rex::platform::detail::GetThreadCount();
        Require(shutdown == 0 && before == after && SDL_WasInit(SDL_INIT_AUDIO) == 0, "app-resources-not-recovered");
        std::cout << "MW3_AUDIO_GATE_COMPLETE:{\"schema\":1,\"nonce\":" << Quote(nonce) << ",\"mode\":" << Quote(mode)
            << ",\"backend\":" << Quote(backend) << ",\"channels\":" << channels
            << ",\"threads_before\":" << before << ",\"threads_after\":" << after
            << ",\"open_after\":0,\"queued_after\":0,\"sdl_audio_after\":0,\"cases\":[";
        for (std::size_t i = 0; i < observations.size(); ++i) { if (i) std::cout << ','; Print(observations[i]); }
        std::cout << "]}\n";
        return failed ? 42 : 0;
    } catch (const std::exception& error) {
        std::cerr << "MW3_AUDIO_GATE_FATAL:" << error.what() << '\n'; app.Shutdown(); return 2;
    }
}
} // namespace
REX_CONSOLE_APP_MAIN(App, Run)
