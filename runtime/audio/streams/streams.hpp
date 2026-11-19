// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <memory>
#include <span>
#include <stdexcept>
#include <thread>

namespace mw3::audio {
using OwnerId = std::uint64_t;
using RawId = std::uint32_t;
inline constexpr std::size_t frame_samples = 6 * 256;
using Frame = std::span<const float, frame_samples>;
using Played = std::function<void()>;

enum class Code {
    invalid_owner, invalid_token, foreign_token, stale_token, wrong_owner,
    wrong_thread, reentrant, closed, capacity, exhausted, invalid_frame,
    callback_fault, backend_contract, invalid_limits
};
class Error final : public std::runtime_error {
public:
    Error(Code code, const char* message) : std::runtime_error(message), code_(code) {}
    [[nodiscard]] Code code() const noexcept { return code_; }
private:
    Code code_;
};

// Host-only port, not a guest service or codec. open returns a unique nonzero
// currently-active raw ID, or throws without retaining a stream. submit copies
// the frame before returning, or throws if refused. close ends callbacks and
// releases the stream. Methods must not reenter the gate. Each binding's played
// callbacks must be serialized (as in the selected SDK mixing contract).
class Backend {
public:
    virtual ~Backend() = default;
    virtual RawId open(Played played) = 0;
    virtual void submit(RawId stream, Frame frame) = 0;
    virtual void close(RawId stream) noexcept = 0;
};
namespace detail { struct Identity; struct CallbackState; }
class Gate;
// Copies support delayed commands; a moved-from/default token is invalid.
// Tokens are lifetime capabilities, not authentication or persistent identities.
class Token final {
public:
    Token() = default;
    Token(const Token&) = default;
    Token& operator=(const Token&) = default;
    Token(Token&&) noexcept = default;
    Token& operator=(Token&&) noexcept = default;
private:
    friend class Gate;
    std::shared_ptr<const detail::Identity> identity_;
    std::size_t slot_ = 0;
    std::uint64_t serial_ = 0;
};
struct Limits {
    std::uint64_t max_bindings = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t max_frames_per_binding = std::numeric_limits<std::uint64_t>::max();
};

// All public operations AND destruction belong to the creating thread. Backend
// outlives Gate; no concurrent destruction. Callback state has an independent
// lifetime and does not refer to this object. No SDK/client call in a callback.
class Gate final {
public:
    static constexpr std::size_t stream_count = 8;
    explicit Gate(Backend& backend, Limits limits = {});
    ~Gate() noexcept;
    Gate(const Gate&) = delete;
    Gate& operator=(const Gate&) = delete;
    Gate(Gate&&) = delete;
    Gate& operator=(Gate&&) = delete;

    [[nodiscard]] Token open(OwnerId owner);
    void submit(const Token& token, OwnerId owner, std::span<const float> frame);
    [[nodiscard]] std::uint64_t take_played(const Token& token, OwnerId owner);
    void close(const Token& token, OwnerId owner);
    void close_owner(OwnerId owner);
    void shutdown();
    [[nodiscard]] std::size_t active_streams() const;

private:
    struct Slot {
        RawId raw = 0;
        OwnerId owner = 0;
        std::uint64_t serial = 0, submitted = 0, seen = 0;
        std::shared_ptr<detail::CallbackState> callback;
    };
    struct Call;
    void check_thread() const;
    void check_live(bool allow_fault = false) const;
    Slot& lookup(const Token&, OwnerId, bool allow_fault = false);
    void check_callback(Slot&);
    RawId detach(Slot&) noexcept;
    void shutdown_impl() noexcept;

    Backend& backend_;
    const Limits limits_;
    const std::thread::id thread_;
    const std::shared_ptr<const detail::Identity> identity_;
    std::array<Slot, stream_count> slots_{};
    std::uint64_t bindings_ = 0;
    bool closed_ = false, faulted_ = false, in_call_ = false;
};
} // namespace mw3::audio
