// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace mw3::storage {

enum class Code {
    invalid_name, unsafe_path, busy, not_owned, corrupt, recovery_required,
    limit, io, transaction, unsupported, uncertain
};

class Error final : public std::runtime_error {
public:
    Error(Code code, const std::string& message);
    [[nodiscard]] Code code() const noexcept { return code_; }
private:
    Code code_;
};

enum class State { missing, ready, recovery_required };

struct ReadResult {
    State state = State::missing;
    std::uint64_t generation = 0;
    std::vector<std::uint8_t> payload;
    std::vector<std::string> diagnostics;
};

// A token belongs to exactly one open Profile session. Destruction does not
// silently commit or erase a pending record: recovery is an explicit operation.
class Transaction final {
public:
    Transaction(Transaction&&) noexcept;
    Transaction& operator=(Transaction&&) noexcept;
    ~Transaction();
    Transaction(const Transaction&) = delete;
    Transaction& operator=(const Transaction&) = delete;
private:
    friend class Profile;
    struct Data;
    explicit Transaction(std::unique_ptr<Data> data);
    std::unique_ptr<Data> data_;
};

// Original host persistence only; this is not an MW3 save format or guest API.
// Single-thread owner, local filesystems, cooperative exclusive writer. Host
// users able to modify the roots outside this API are outside its trust boundary.
class Profile final {
public:
    static constexpr std::size_t max_payload = 1024 * 1024;
    static constexpr std::size_t max_entries = 256;

    // Both roots must exist, be absolute, contain no links/reparse components,
    // and be disjoint. create never adopts an existing profile directory.
    static Profile create(const std::filesystem::path& writable_base,
                          const std::filesystem::path& prepared_content,
                          const std::string& profile_id);
    static Profile open(const std::filesystem::path& writable_base,
                        const std::filesystem::path& prepared_content,
                        const std::string& profile_id);
    Profile(Profile&&) noexcept;
    Profile& operator=(Profile&&) noexcept;
    ~Profile();
    Profile(const Profile&) = delete;
    Profile& operator=(const Profile&) = delete;

    [[nodiscard]] Transaction stage(const std::string& slot,
                                    std::span<const std::uint8_t> payload);
    void commit(Transaction& transaction);
    void rollback(Transaction& transaction);
    [[nodiscard]] ReadResult load(const std::string& slot) const;
    // Retain pending/invalid newest records as .rejected; never promote a
    // pending record. Return the most recent valid committed generation.
    [[nodiscard]] ReadResult recover(const std::string& slot);

private:
    struct Impl;
    explicit Profile(std::unique_ptr<Impl> impl);
    static Profile acquire(const std::filesystem::path&, const std::filesystem::path&,
                           const std::string&, bool create);
    std::unique_ptr<Impl> impl_;
};

} // namespace mw3::storage
