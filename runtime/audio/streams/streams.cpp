// SPDX-License-Identifier: GPL-3.0-only
#include "streams.hpp"
#include <atomic>
#include <exception>

namespace mw3::audio {
namespace detail {
struct Identity {};
struct CallbackState {
    explicit CallbackState(std::uint64_t maximum) : limit(maximum) {}
    const std::uint64_t limit;
    std::atomic<bool> active{false}, fault{false};
    std::atomic<std::uint64_t> played{0};
    void notify() noexcept {
        if (!active.load(std::memory_order_acquire)) return;
        // Exactly one serialized producer per binding; the owner only loads.
        // No CAS spin, locks, resets, allocations, SDK or client calls here.
        const auto previous = played.load(std::memory_order_relaxed);
        if (previous >= limit) { fault.store(true, std::memory_order_release); return; }
        played.store(previous + 1, std::memory_order_release);
    }
};
} // namespace detail
namespace {
[[noreturn]] void fail(Code code, const char* message) { throw Error(code, message); }
void owner_check(OwnerId owner) { if (!owner) fail(Code::invalid_owner, "Host owner ID must be nonzero"); }
}
struct Gate::Call {
    Gate& gate;
    explicit Call(Gate& source) : gate(source) {
        gate.check_thread();
        if (gate.in_call_) fail(Code::reentrant, "Backend reentered audio admission");
        gate.in_call_ = true;
    }
    ~Call() { gate.in_call_ = false; }
};
Gate::Gate(Backend& backend, Limits limits)
    : backend_(backend), limits_(limits), thread_(std::this_thread::get_id()),
      identity_(std::make_shared<detail::Identity>()) {
    if (!limits.max_bindings || !limits.max_frames_per_binding)
        fail(Code::invalid_limits, "Audio lifetime budgets must be nonzero");
}
Gate::~Gate() noexcept {
    // A thread-affine object's lifetime is a caller precondition. Do not make
    // unsafe backend calls if that lifetime contract has been violated.
    if (std::this_thread::get_id() != thread_ || in_call_) std::terminate();
    shutdown_impl();
}
void Gate::check_thread() const {
    if (std::this_thread::get_id() != thread_) fail(Code::wrong_thread, "Audio gate belongs to another host thread");
}
void Gate::check_live(bool allow_fault) const {
    if (closed_) fail(Code::closed, "Audio gate is shut down");
    if (faulted_ && !allow_fault) fail(Code::backend_contract, "Audio backend identity contract failed; shutdown required");
}
Gate::Slot& Gate::lookup(const Token& token, OwnerId owner, bool allow_fault) {
    check_live(allow_fault);
    owner_check(owner);
    if (!token.identity_) fail(Code::invalid_token, "Default or moved audio token");
    if (token.identity_ != identity_) fail(Code::foreign_token, "Audio token belongs to another gate instance");
    if (token.slot_ >= stream_count || !token.serial_) fail(Code::invalid_token, "Invalid audio token");
    auto& slot = slots_[token.slot_];
    if (!slot.raw || slot.serial != token.serial_) fail(Code::stale_token, "Closed or replaced audio token");
    if (slot.owner != owner) fail(Code::wrong_owner, "Audio token belongs to another host owner");
    return slot;
}
void Gate::check_callback(Slot& slot) {
    if (slot.callback->fault.load(std::memory_order_acquire) ||
        slot.callback->played.load(std::memory_order_acquire) > slot.submitted) {
        slot.callback->fault.store(true, std::memory_order_release);
        fail(Code::callback_fault, "Audio completion count exceeded accepted frames or its lifetime budget");
    }
}
Token Gate::open(OwnerId owner) {
    Call call(*this);
    check_live(); owner_check(owner);
    if (bindings_ >= limits_.max_bindings) fail(Code::exhausted, "Audio binding lifetime budget exhausted");
    std::size_t index = 0;
    while (index < stream_count && slots_[index].raw) ++index;
    if (index == stream_count) fail(Code::capacity, "Eight host audio streams already owned");
    auto callback = std::make_shared<detail::CallbackState>(limits_.max_frames_per_binding);
    const auto raw = backend_.open([callback] { callback->notify(); });
    bool duplicate = raw == 0;
    for (const auto& slot : slots_) duplicate = duplicate || (raw != 0 && slot.raw == raw);
    if (duplicate) {
        // Closing an ambiguous duplicate could destroy an earlier valid owner.
        // Stop admission; retain those owned mappings for explicit shutdown.
        faulted_ = true;
        fail(Code::backend_contract, "Backend returned a zero or already-active raw audio ID");
    }
    ++bindings_; // Checked before backend call; cannot wrap.
    auto& slot = slots_[index];
    slot.raw = raw; slot.owner = owner; slot.serial = bindings_;
    slot.callback = std::move(callback);
    slot.callback->active.store(true, std::memory_order_release);
    Token token;
    token.identity_ = identity_; token.slot_ = index; token.serial_ = bindings_;
    return token;
}
void Gate::submit(const Token& token, OwnerId owner, std::span<const float> frame) {
    Call call(*this);
    auto& slot = lookup(token, owner);
    check_callback(slot);
    if (frame.size() != frame_samples) fail(Code::invalid_frame, "Host PCM frame must contain six by 256 float samples");
    if (slot.submitted >= limits_.max_frames_per_binding) fail(Code::exhausted, "Audio frame lifetime budget exhausted");
    // Backend refusal propagates; no counter or ownership state is advanced.
    // A callback may arrive during this call; owner polling cannot reenter it.
    backend_.submit(slot.raw, Frame(frame.data(), frame_samples));
    ++slot.submitted;
}
std::uint64_t Gate::take_played(const Token& token, OwnerId owner) {
    Call call(*this);
    auto& slot = lookup(token, owner);
    check_callback(slot);
    const auto total = slot.callback->played.load(std::memory_order_acquire);
    if (total < slot.seen || total > slot.submitted || slot.callback->fault.load(std::memory_order_acquire)) {
        slot.callback->fault.store(true, std::memory_order_release);
        fail(Code::callback_fault, "Invalid audio completion observation");
    }
    const auto delta = total - slot.seen;
    slot.seen = total;
    return delta;
}
RawId Gate::detach(Slot& slot) noexcept {
    const auto raw = slot.raw;
    if (slot.callback) slot.callback->active.store(false, std::memory_order_release);
    slot = Slot{};
    return raw;
}
void Gate::close(const Token& token, OwnerId owner) {
    Call call(*this);
    auto& slot = lookup(token, owner, true);
    const auto raw = detach(slot);
    backend_.close(raw);
}
void Gate::close_owner(OwnerId owner) {
    Call call(*this);
    check_live(true); owner_check(owner);
    std::array<RawId, stream_count> closing{};
    for (std::size_t i = 0; i < stream_count; ++i)
        if (slots_[i].raw && slots_[i].owner == owner) closing[i] = detach(slots_[i]);
    // All affected lifetimes are invalid before the first backend close.
    for (const auto raw : closing) if (raw) backend_.close(raw);
}
void Gate::shutdown_impl() noexcept {
    closed_ = true;
    std::array<RawId, stream_count> closing{};
    for (std::size_t i = 0; i < stream_count; ++i) if (slots_[i].raw) closing[i] = detach(slots_[i]);
    for (const auto raw : closing) if (raw) backend_.close(raw);
}
void Gate::shutdown() {
    Call call(*this);
    shutdown_impl();
}
std::size_t Gate::active_streams() const {
    check_thread();
    std::size_t count = 0;
    for (const auto& slot : slots_) if (slot.raw) ++count;
    return count;
}
} // namespace mw3::audio
