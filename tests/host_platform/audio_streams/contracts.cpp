// SPDX-License-Identifier: GPL-3.0-only
// Original model/fault tests. These do not execute an SDK or prove playback.
#include "streams.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <new>
#include <semaphore>
#include <string>
#include <thread>
#include <utility>
#ifdef _WIN32
#include <malloc.h>
#endif

namespace { std::atomic<std::uint64_t> allocations{0}; }
void* operator new(std::size_t size) {
    allocations.fetch_add(1, std::memory_order_relaxed);
    if (void* p = std::malloc(size ? size : 1)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
void* operator new(std::size_t size, std::align_val_t alignment) {
    allocations.fetch_add(1, std::memory_order_relaxed);
#ifdef _WIN32
    if (void* p = _aligned_malloc(size ? size : 1, static_cast<std::size_t>(alignment))) return p;
#else
    void* p = nullptr;
    if (posix_memalign(&p, static_cast<std::size_t>(alignment), size ? size : 1) == 0) return p;
#endif
    throw std::bad_alloc();
}
void* operator new[](std::size_t size, std::align_val_t alignment) { return ::operator new(size, alignment); }
void operator delete(void* p, std::align_val_t) noexcept {
#ifdef _WIN32
    _aligned_free(p);
#else
    std::free(p);
#endif
}
void operator delete[](void* p, std::align_val_t a) noexcept { ::operator delete(p, a); }
void operator delete(void* p, std::size_t, std::align_val_t a) noexcept { ::operator delete(p, a); }
void operator delete[](void* p, std::size_t, std::align_val_t a) noexcept { ::operator delete(p, a); }

namespace {
namespace a = mw3::audio;
using PCM = std::array<float, a::frame_samples>;
void Check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void Reject(a::Code expected, F&& action) {
    try { action(); }
    catch (const a::Error& error) { Check(error.code() == expected, "wrong rejection category"); return; }
    throw std::runtime_error("expected admission rejection");
}
template<class F> void BackendFailure(F&& action) {
    try { action(); } catch (const std::runtime_error& e) {
        Check(std::string(e.what()) == "original model backend refusal", "backend error changed"); return;
    }
    throw std::runtime_error("backend refusal was swallowed");
}
struct Model final : a::Backend {
    std::array<a::Played, 8> callbacks{};
    unsigned opens = 0, submits = 0, closes = 0, bad_closes = 0;
    bool refuse_open = false, refuse_submit = false, immediate = true;
    a::RawId override_id = 0;
    bool override_next = false;
    a::Played abandoned;
    std::function<void()> enter;
    const float* expected_data = nullptr;
    a::RawId open(a::Played cb) override {
        ++opens;
        if (enter) enter();
        if (refuse_open) throw std::runtime_error("original model backend refusal");
        if (override_next) { override_next = false; abandoned = std::move(cb); return override_id; }
        for (std::size_t i = 0; i < callbacks.size(); ++i) {
            if (!callbacks[i]) { callbacks[i] = std::move(cb); return static_cast<a::RawId>(i + 1); }
        }
        throw std::runtime_error("original model backend refusal");
    }
    void submit(a::RawId id, a::Frame frame) override {
        ++submits;
        if (enter) enter();
        if (refuse_submit) throw std::runtime_error("original model backend refusal");
        Check(id && id <= 8 && bool(callbacks[id - 1]), "model received unknown raw ID");
        if (expected_data) Check(frame.data() == expected_data, "gate copied PCM instead of forwarding its span");
        if (immediate) callbacks[id - 1]();
    }
    void close(a::RawId id) noexcept override {
        ++closes;
        if (!id || id > 8 || !callbacks[id - 1]) { ++bad_closes; return; }
        callbacks[id - 1] = {};
    }
    unsigned active() const {
        return static_cast<unsigned>(std::count_if(callbacks.begin(), callbacks.end(), [](const auto& cb) { return bool(cb); }));
    }
};
void Lifetime() {
    Model b; PCM frame{}; a::Played old_callback;
    {
        a::Gate g(b);
        auto old = g.open(11); old_callback = b.callbacks[0];
        g.submit(old, 11, frame); Check(g.take_played(old, 11) == 1, "initial credit");
        Check(g.take_played(old, 11) == 0, "credit counted twice");
        g.close(old, 11);
        auto replacement = g.open(22);
        const auto calls = b.submits;
        Reject(a::Code::stale_token, [&] { g.submit(old, 11, frame); });
        Reject(a::Code::stale_token, [&] { (void)g.take_played(old, 11); });
        Reject(a::Code::stale_token, [&] { g.close(old, 11); });
        Check(b.submits == calls && b.closes == 1, "stale command reached backend");
        old_callback(); // Deliberately retained model callback, not an SDK observation.
        Check(g.take_played(replacement, 22) == 0, "late callback credited replacement");
        g.submit(replacement, 22, frame);
        Check(g.take_played(replacement, 22) == 1, "replacement failed to progress");
        auto moved = std::move(replacement);
        Reject(a::Code::invalid_token, [&] { g.submit(replacement, 22, frame); });
        g.close(moved, 22);
    }
    old_callback();
    Check(!b.active() && b.closes == 2 && !b.bad_closes, "lifetime resource recovery");
}
void Owners() {
    Model b, other; PCM frame{};
    a::Gate g(b), foreign(other);
    auto x = g.open(1), y = g.open(2), z = g.open(1), f = foreign.open(1);
    Reject(a::Code::invalid_owner, [&] { (void)g.open(0); });
    Reject(a::Code::invalid_token, [&] { g.submit(a::Token{}, 1, frame); });
    Reject(a::Code::foreign_token, [&] { g.submit(f, 1, frame); });
    Reject(a::Code::foreign_token, [&] { foreign.submit(x, 1, frame); });
    Reject(a::Code::wrong_owner, [&] { g.submit(x, 2, frame); });
    Reject(a::Code::wrong_owner, [&] { g.close(y, 1); });
    Check(!b.submits && !other.submits && !b.closes, "bad owner/instance command reached backend");
    g.close_owner(1);
    Check(b.active() == 1 && g.active_streams() == 1 && !b.callbacks[0] && !b.callbacks[2], "owner-close crossed owners");
    Reject(a::Code::stale_token, [&] { g.submit(z, 1, frame); });
    g.submit(y, 2, frame); foreign.submit(f, 1, frame);
    Check(g.take_played(y, 2) == 1 && foreign.take_played(f, 1) == 1, "other owner/instance stopped");
    g.shutdown(); foreign.shutdown();
    Check(!b.active() && !other.active() && !b.bad_closes && !other.bad_closes, "owner cleanup");
}
void Failures() {
    Model b; PCM frame{}; a::Gate g(b);
    auto x = g.open(1);
    b.refuse_open = true; BackendFailure([&] { (void)g.open(2); }); b.refuse_open = false;
    Check(g.active_streams() == 1 && b.active() == 1 && b.closes == 0, "partial-open rollback changed prior owner");
    b.refuse_submit = true; BackendFailure([&] { g.submit(x, 1, frame); }); b.refuse_submit = false;
    Check(g.take_played(x, 1) == 0, "refused frame credited");
    g.submit(x, 1, frame); Check(g.take_played(x, 1) == 1, "submit failure poisoned valid owner");
    b.override_next = true; b.override_id = 1;
    Reject(a::Code::backend_contract, [&] { (void)g.open(2); });
    Check(b.closes == 0 && b.active() == 1 && g.active_streams() == 1, "ambiguous duplicate closed prior owner");
    const auto submits = b.submits;
    Reject(a::Code::backend_contract, [&] { g.submit(x, 1, frame); });
    Check(b.submits == submits, "faulted backend still admitted submissions");
    g.shutdown(); Check(!b.active() && b.closes == 1 && !b.bad_closes, "duplicate raw cleanup");
    Model zero; a::Gate h(zero); zero.override_next = true;
    Reject(a::Code::backend_contract, [&] { (void)h.open(1); });
    h.shutdown(); Check(zero.closes == 0, "unknown zero raw ID was closed");
}
void Credits() {
    Model b; PCM frame{}; a::Gate g(b, {8, 2});
    auto x = g.open(1), y = g.open(2);
    g.submit(x, 1, frame); g.submit(x, 1, frame);
    Check(g.take_played(x, 1) == 2, "completion total");
    const auto calls = b.submits;
    Reject(a::Code::exhausted, [&] { g.submit(x, 1, frame); });
    Check(b.submits == calls, "frame budget wrapped or reached backend");
    b.callbacks[0](); // Model violates the completion budget; it must latch a fault.
    Reject(a::Code::callback_fault, [&] { (void)g.take_played(x, 1); });
    Reject(a::Code::callback_fault, [&] { g.submit(x, 1, frame); });
    g.submit(y, 2, frame); Check(g.take_played(y, 2) == 1, "completion fault crossed owners");
    g.close(x, 1); g.close(y, 2);
    Model unexpected; a::Gate h(unexpected); auto z = h.open(3);
    unexpected.callbacks[0]();
    Reject(a::Code::callback_fault, [&] { (void)h.take_played(z, 3); });
    h.close(z, 3);
}
void Limits() {
    Model b; a::Gate g(b);
    std::array<a::Token, 8> tokens;
    for (std::size_t i = 0; i < tokens.size(); ++i) tokens[i] = g.open(i + 1);
    const auto before = b.opens;
    Reject(a::Code::capacity, [&] { (void)g.open(9); });
    Check(b.opens == before, "capacity rejection called backend");
    g.shutdown(); Check(b.closes == 8 && !b.bad_closes, "capacity recovery");
    Model limited; a::Gate h(limited, {2, 10});
    auto x = h.open(1); h.close(x, 1);
    limited.refuse_open = true; BackendFailure([&] { (void)h.open(2); }); limited.refuse_open = false;
    auto y = h.open(2); h.close(y, 2);
    const auto attempts = limited.opens;
    Reject(a::Code::exhausted, [&] { (void)h.open(3); });
    Check(limited.opens == attempts, "binding budget wrapped or failed-open consumed serial");
    Reject(a::Code::invalid_limits, [&] { a::Gate invalid(limited, {0, 1}); });
    Reject(a::Code::invalid_limits, [&] { a::Gate invalid(limited, {1, 0}); });
}
void Frames() {
    Model b; a::Gate g(b); const auto t = g.open(1);
    std::array<float, a::frame_samples + 1> buffer{};
    for (const auto size : {std::size_t{0}, std::size_t{1}, a::frame_samples - 1, a::frame_samples + 1})
        Reject(a::Code::invalid_frame, [&] { g.submit(t, 1, std::span(buffer).first(size)); });
    Check(b.submits == 0, "invalid frame reached backend");
    buffer[0] = std::bit_cast<float>(std::uint32_t{0x7fc01234});
    b.expected_data = buffer.data();
    g.submit(t, 1, std::span(buffer).first(a::frame_samples));
    Check(g.take_played(t, 1) == 1 && std::bit_cast<std::uint32_t>(buffer[0]) == 0x7fc01234,
          "ownership gate normalized or copied PCM");
}
void Threads() {
    Model b; PCM frame{}; a::Gate g(b); auto token = g.open(1);
    std::array<bool, 7> rejected{};
    std::thread wrong([&] {
        const auto check = [&](std::size_t index, auto&& action) {
            try { action(); } catch (const a::Error& error) { rejected[index] = error.code() == a::Code::wrong_thread; }
        };
        check(0, [&] { (void)g.open(1); }); check(1, [&] { g.submit(token, 1, frame); });
        check(2, [&] { (void)g.take_played(token, 1); }); check(3, [&] { g.close(token, 1); });
        check(4, [&] { g.close_owner(1); }); check(5, [&] { g.shutdown(); });
        check(6, [&] { (void)g.active_streams(); });
    });
    wrong.join();
    Check(std::all_of(rejected.begin(), rejected.end(), [](bool value) { return value; }), "wrong-thread call accepted");
    Check(b.opens == 1 && !b.submits && !b.closes, "wrong thread reached backend");
    b.immediate = false;
    const auto played = b.callbacks[0];
    std::counting_semaphore<1024> work{0}, completed{0};
    std::thread producer([&] { for (unsigned i = 0; i < 256; ++i) { work.acquire(); played(); completed.release(); } });
    std::uint64_t observed = 0;
    for (unsigned batch = 0; batch < 16; ++batch) {
        for (unsigned i = 0; i < 16; ++i) { g.submit(token, 1, frame); work.release(); }
        for (unsigned i = 0; i < 16; ++i) completed.acquire();
        observed += g.take_played(token, 1);
    }
    producer.join();
    Check(observed == 256 && g.take_played(token, 1) == 0, "serialized producer credit conservation");
    g.close(token, 1);
}
void Shutdown() {
    Model b; PCM frame{}; a::Token expired;
    {
        a::Gate g(b); expired = g.open(1); (void)g.open(2);
        g.shutdown(); g.shutdown();
        Check(g.active_streams() == 0 && b.closes == 2, "shutdown was not idempotent");
        Reject(a::Code::closed, [&] { (void)g.open(1); });
        Reject(a::Code::closed, [&] { g.submit(expired, 1, frame); });
    }
    Check(!b.active() && b.closes == 2 && !b.bad_closes, "shutdown destructor double-close");
    {
        a::Gate fresh(b); const auto current = fresh.open(1);
        Reject(a::Code::foreign_token, [&] { fresh.submit(expired, 1, frame); });
        fresh.submit(current, 1, frame);
    }
    Check(!b.active() && b.closes == 3, "destructor did not release owned stream");
}
void Reentrancy() {
    Model b; a::Gate g(b);
    b.enter = [&] { (void)g.open(2); };
    Reject(a::Code::reentrant, [&] { (void)g.open(1); });
    Check(b.opens == 1 && g.active_streams() == 0, "reentrant open reached backend twice or leaked");
    b.enter = {};
    auto t = g.open(1); PCM frame{};
    b.enter = [&] { g.close(t, 1); };
    Reject(a::Code::reentrant, [&] { g.submit(t, 1, frame); });
    Check(!b.closes && g.active_streams() == 1, "reentrant close changed live owner");
    b.enter = {};
    g.submit(t, 1, frame); Check(g.take_played(t, 1) == 1, "reentry failure advanced accepted count");
}
void Benchmark() {
    Model b; a::Gate g(b); PCM frame{}; b.expected_data = frame.data();
    const auto token = g.open(1);
    for (unsigned i = 0; i < 256; ++i) g.submit(token, 1, frame);
    Check(g.take_played(token, 1) == 256, "benchmark warmup credit count");
    constexpr std::size_t samples = 4096, batch = 64;
    std::array<std::uint64_t, samples> ns{};
    const auto before = allocations.load(std::memory_order_relaxed);
    for (std::size_t i = 0; i < samples; ++i) {
        const auto start = std::chrono::steady_clock::now();
        for (std::size_t n = 0; n < batch; ++n) g.submit(token, 1, frame);
        ns[i] = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count());
        Check(g.take_played(token, 1) == batch, "benchmark must conserve played credits");
    }
    const auto allocated = allocations.load(std::memory_order_relaxed) - before;
    Check(allocated == 0 && b.submits == 256 + samples * batch, "normal ownership admission allocated or skipped work");
    std::cout << "SYNTHETIC_AUDIO_GATE:{\"warmup\":256,\"batch\":64,\"allocations\":" << allocated << ",\"batch_ns\":[";
    for (std::size_t i = 0; i < ns.size(); ++i) { if (i) std::cout << ','; std::cout << ns[i]; }
    std::cout << "]}\n";
}
} // namespace
int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "ERROR: exactly one case required\n"; return 2; }
    const std::string name(argv[1]);
    try {
        if (name == "lifetime") Lifetime();
        else if (name == "owners") Owners();
        else if (name == "failures") Failures();
        else if (name == "credits") Credits();
        else if (name == "limits") Limits();
        else if (name == "frames") Frames();
        else if (name == "threads") Threads();
        else if (name == "shutdown") Shutdown();
        else if (name == "reentrancy") Reentrancy();
        else if (name == "benchmark") Benchmark();
        else if (name == "wrong-result") { Lifetime(); throw std::runtime_error("deliberate wrong-result rejected"); }
        else { std::cerr << "ERROR: unknown case\n"; return 2; }
        std::cout << "PASS: original host audio gate " << name << "; SDK/title playback NOT TESTED\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
