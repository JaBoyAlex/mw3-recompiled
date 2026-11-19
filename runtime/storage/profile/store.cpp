// SPDX-License-Identifier: GPL-3.0-only
#include "store.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstring>
#include <limits>
#include <optional>
#include <utility>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#if !defined(__linux__)
#error "Profile publication requires the Linux no-replace rename contract"
#endif
#include <dirent.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace mw3::storage {
namespace {
[[noreturn]] void fail(Code code, const std::string& message) { throw Error(code, message); }

void name_check(const std::string& name) {
    const auto alnum = [](char c) { return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'); };
    if (name.empty() || name.size() > 32 || !alnum(name.front()) ||
        !std::all_of(name.begin(), name.end(), [&](char c) { return alnum(c) || c == '_' || c == '-'; }))
        fail(Code::invalid_name, "Names require 1..32 canonical lowercase ASCII characters");
    if (name == "con" || name == "prn" || name == "aux" || name == "nul" ||
        (name.size() == 4 && (name.starts_with("com") || name.starts_with("lpt")) &&
         name[3] >= '0' && name[3] <= '9'))
        fail(Code::invalid_name, "Reserved device name");
}

void path_check(const std::filesystem::path& path) {
    if (!path.is_absolute() || path.native().size() > 4096 ||
        path.native().find(typename std::filesystem::path::value_type{}) != std::filesystem::path::string_type::npos)
        fail(Code::unsafe_path, "Root must be a bounded absolute path without NUL");
    std::size_t count = 0;
    for (const auto& part : path.relative_path()) {
        if (++count > 128 || part == "." || part == "..") fail(Code::unsafe_path, "Unsafe root component");
    }
#ifdef _WIN32
    const auto drive = path.root_name().native();
    if (drive.size() != 2 || drive[1] != L':' ||
        !((drive[0] >= L'A' && drive[0] <= L'Z') || (drive[0] >= L'a' && drive[0] <= L'z')))
        fail(Code::unsupported, "Only local drive roots are supported");
    for (const auto& part : path.relative_path()) {
        const auto s = part.native();
        if (!s.empty() && (s.back() == L'.' || s.back() == L' ' || s.find(L':') != std::wstring::npos))
            fail(Code::unsafe_path, "Ambiguous Windows root component");
    }
#endif
}

#ifdef _WIN32
struct Handle {
    HANDLE value = INVALID_HANDLE_VALUE;
    Handle() = default;
    explicit Handle(HANDLE v) : value(v) {}
    Handle(Handle&& other) noexcept : value(std::exchange(other.value, INVALID_HANDLE_VALUE)) {}
    Handle& operator=(Handle&& other) noexcept {
        if (this != &other) { reset(); value = std::exchange(other.value, INVALID_HANDLE_VALUE); }
        return *this;
    }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    ~Handle() { reset(); }
    void reset() noexcept { if (value != INVALID_HANDLE_VALUE) { CloseHandle(value); value = INVALID_HANDLE_VALUE; } }
};
using Identity = std::array<DWORD, 3>;
BY_HANDLE_FILE_INFORMATION info(const Handle& handle, bool directory) {
    BY_HANDLE_FILE_INFORMATION result{};
    if (!GetFileInformationByHandle(handle.value, &result)) fail(Code::io, "Cannot query handle identity");
    if ((result.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0 ||
        ((result.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) != directory ||
        (!directory && (result.nNumberOfLinks != 1 || GetFileType(handle.value) != FILE_TYPE_DISK)))
        fail(Code::unsafe_path, "Link, reparse or nonregular entry refused");
    return result;
}
Identity identity(const Handle& handle) {
    const auto i = info(handle, true);
    return {i.dwVolumeSerialNumber, i.nFileIndexHigh, i.nFileIndexLow};
}
struct Directory {
    std::filesystem::path path;
    std::vector<Handle> pins;
    std::vector<Identity> ancestry;
    static Directory root(const std::filesystem::path& path) {
        path_check(path);
        Directory result;
        auto current = path.root_path();
        const auto pin = [&] {
            Handle h(CreateFileW(current.c_str(), FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING,
                                 FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            if (h.value == INVALID_HANDLE_VALUE) fail(Code::unsafe_path, "Cannot pin root component");
            result.ancestry.push_back(identity(h));
            result.pins.push_back(std::move(h));
        };
        pin();
        for (const auto& part : path.relative_path()) {
            if (part.empty()) continue;
            current /= part;
            pin();
        }
        result.path = current;
        return result;
    }
    Directory child(const std::string& name, bool create) const {
        const auto target = path / name;
        if (create && !CreateDirectoryW(target.c_str(), nullptr))
            fail(Code::not_owned, "Profile already exists or cannot be created; never adopt original saves");
        return root(target);
    }
    Handle file(const std::string& name, DWORD access, DWORD disposition, bool exclusive = false) const {
        Handle h(CreateFileW((path / name).c_str(), access, exclusive ? 0 : FILE_SHARE_READ,
                             nullptr, disposition, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT |
                             FILE_FLAG_BACKUP_SEMANTICS, nullptr));
        if (h.value == INVALID_HANDLE_VALUE) {
            const auto e = GetLastError();
            fail(e == ERROR_SHARING_VIOLATION ? Code::busy : Code::io, "Cannot open owned file: " + name);
        }
        (void)info(h, false);
        return h;
    }
    void check_file(const std::string& name) const { (void)file(name, FILE_READ_ATTRIBUTES, OPEN_EXISTING); }
    std::vector<std::string> list() const {
        WIN32_FIND_DATAW data{};
        const auto find = FindFirstFileW((path / L"*").c_str(), &data);
        if (find == INVALID_HANDLE_VALUE) fail(Code::io, "Cannot enumerate owned profile");
        std::vector<std::string> result;
        try {
            do {
                const std::wstring leaf(data.cFileName);
                if (leaf == L"." || leaf == L"..") continue;
                if (result.size() >= Profile::max_entries) fail(Code::limit, "Profile entry budget exceeded");
                std::string ascii;
                for (const auto c : leaf) {
                    if (c < 0x20 || c > 0x7e) fail(Code::unsafe_path, "Noncanonical profile entry");
                    ascii.push_back(static_cast<char>(c));
                }
                result.push_back(std::move(ascii));
            } while (FindNextFileW(find, &data));
            if (GetLastError() != ERROR_NO_MORE_FILES) fail(Code::io, "Profile enumeration failed");
        } catch (...) { FindClose(find); throw; }
        FindClose(find);
        return result;
    }
    std::vector<std::uint8_t> read(const std::string& name, std::size_t bound) const {
        auto h = file(name, GENERIC_READ, OPEN_EXISTING);
        const auto before = info(h, false);
        const auto size = (static_cast<std::uint64_t>(before.nFileSizeHigh) << 32) | before.nFileSizeLow;
        if (size > bound) fail(Code::corrupt, "Oversized owned file: " + name);
        std::vector<std::uint8_t> result(static_cast<std::size_t>(size));
        DWORD done = 0;
        if (!ReadFile(h.value, result.data(), static_cast<DWORD>(result.size()), &done, nullptr) || done != result.size())
            fail(Code::io, "Incomplete owned read: " + name);
        const auto after = info(h, false);
        if (before.nFileSizeHigh != after.nFileSizeHigh || before.nFileSizeLow != after.nFileSizeLow ||
            CompareFileTime(&before.ftLastWriteTime, &after.ftLastWriteTime) != 0)
            fail(Code::corrupt, "Owned file changed during read: " + name);
        return result;
    }
    void write_new(const std::string& name, std::span<const std::uint8_t> bytes) const {
        auto h = file(name, GENERIC_WRITE, CREATE_NEW);
        DWORD done = 0;
        if (!WriteFile(h.value, bytes.data(), static_cast<DWORD>(bytes.size()), &done, nullptr) || done != bytes.size() ||
            !FlushFileBuffers(h.value)) fail(Code::io, "Owned write/flush failed; retain pending bytes: " + name);
        const auto raw = std::exchange(h.value, INVALID_HANDLE_VALUE);
        if (!CloseHandle(raw)) fail(Code::io, "Owned close failed: " + name);
    }
    Handle lock() const { return file(".lock", GENERIC_READ | GENERIC_WRITE, OPEN_ALWAYS, true); }
    void publish(const std::string& from, const std::string& to) const {
        check_file(from);
        if (!MoveFileExW((path / from).c_str(), (path / to).c_str(), MOVEFILE_WRITE_THROUGH))
            fail(Code::io, "No-replace publication failed; source retained: " + from);
    }
    void sync() const {
        // Windows does not expose a portable directory-fsync durability promise.
        // File flushing + same-volume write-through rename is process-recovery
        // evidence only; power-loss durability is explicitly outside this API.
    }
};
#else
struct Handle {
    int value = -1;
    Handle() = default;
    explicit Handle(int v) : value(v) {}
    Handle(Handle&& other) noexcept : value(std::exchange(other.value, -1)) {}
    Handle& operator=(Handle&& other) noexcept {
        if (this != &other) { reset(); value = std::exchange(other.value, -1); }
        return *this;
    }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    ~Handle() { reset(); }
    void reset() noexcept { if (value >= 0) { (void)::close(value); value = -1; } }
};
using Identity = std::array<std::uint64_t, 2>;
struct stat info(const Handle& handle, bool directory) {
    struct stat result{};
    if (::fstat(handle.value, &result) != 0) fail(Code::io, "Cannot query handle identity");
    if ((directory ? !S_ISDIR(result.st_mode) : !S_ISREG(result.st_mode)) ||
        (!directory && result.st_nlink != 1)) fail(Code::unsafe_path, "Link or nonregular entry refused");
    return result;
}
Identity identity(const Handle& handle) {
    const auto i = info(handle, true);
    return {static_cast<std::uint64_t>(i.st_dev), static_cast<std::uint64_t>(i.st_ino)};
}
struct Directory {
    Handle handle;
    std::vector<Identity> ancestry;
    static Directory root(const std::filesystem::path& path) {
        path_check(path);
        Directory result;
        result.handle = Handle(::open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
        if (result.handle.value < 0) fail(Code::unsafe_path, "Cannot pin filesystem root");
        result.ancestry.push_back(identity(result.handle));
        for (const auto& part : path.relative_path()) {
            if (part.empty()) continue;
            Handle next(::openat(result.handle.value, part.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
            if (next.value < 0) fail(Code::unsafe_path, "Cannot pin root component");
            result.ancestry.push_back(identity(next));
            result.handle = std::move(next);
        }
        return result;
    }
    Directory child(const std::string& name, bool create) const {
        if (create && ::mkdirat(handle.value, name.c_str(), 0700) != 0)
            fail(Code::not_owned, "Profile already exists or cannot be created; never adopt original saves");
        Directory result;
        result.handle = Handle(::openat(handle.value, name.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
        if (result.handle.value < 0) fail(Code::unsafe_path, "Unsafe profile directory");
        (void)info(result.handle, true);
        return result;
    }
    Handle file(const std::string& name, int flags) const {
        Handle h(::openat(handle.value, name.c_str(), flags | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK, 0600));
        if (h.value < 0) fail(errno == ELOOP ? Code::unsafe_path : Code::io, "Cannot open owned file: " + name);
        (void)info(h, false);
        return h;
    }
    void check_file(const std::string& name) const { (void)file(name, O_RDONLY); }
    std::vector<std::string> list() const {
        const int copy = ::openat(handle.value, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (copy < 0) fail(Code::io, "Cannot open directory enumeration");
        DIR* stream = ::fdopendir(copy);
        if (!stream) { ::close(copy); fail(Code::io, "Cannot enumerate owned profile"); }
        std::vector<std::string> result;
        try {
            errno = 0;
            while (const auto* entry = ::readdir(stream)) {
                const std::string name(entry->d_name);
                if (name == "." || name == "..") continue;
                if (result.size() >= Profile::max_entries) fail(Code::limit, "Profile entry budget exceeded");
                result.push_back(name);
                errno = 0;
            }
            if (errno != 0) fail(Code::io, "Profile enumeration failed");
        } catch (...) { ::closedir(stream); throw; }
        ::closedir(stream);
        return result;
    }
    std::vector<std::uint8_t> read(const std::string& name, std::size_t bound) const {
        auto h = file(name, O_RDONLY);
        const auto before = info(h, false);
        if (before.st_size < 0 || static_cast<std::uint64_t>(before.st_size) > bound)
            fail(Code::corrupt, "Oversized owned file: " + name);
        std::vector<std::uint8_t> result(static_cast<std::size_t>(before.st_size));
        std::size_t offset = 0;
        while (offset < result.size()) {
            const auto n = ::read(h.value, result.data() + offset, result.size() - offset);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) fail(Code::io, "Incomplete owned read: " + name);
            offset += static_cast<std::size_t>(n);
        }
        const auto after = info(h, false);
        if (before.st_size != after.st_size || before.st_mtim.tv_sec != after.st_mtim.tv_sec ||
            before.st_mtim.tv_nsec != after.st_mtim.tv_nsec)
            fail(Code::corrupt, "Owned file changed during read: " + name);
        return result;
    }
    void write_new(const std::string& name, std::span<const std::uint8_t> bytes) const {
        auto h = file(name, O_WRONLY | O_CREAT | O_EXCL);
        std::size_t offset = 0;
        while (offset < bytes.size()) {
            const auto n = ::write(h.value, bytes.data() + offset, bytes.size() - offset);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) fail(Code::io, "Owned write failed; retain pending bytes: " + name);
            offset += static_cast<std::size_t>(n);
        }
        if (::fsync(h.value) != 0) fail(Code::io, "Owned file flush failed: " + name);
        const int raw = std::exchange(h.value, -1);
        if (::close(raw) != 0) fail(Code::io, "Owned file close failed: " + name);
    }
    Handle lock() const {
        auto h = file(".lock", O_RDWR | O_CREAT);
        if (::flock(h.value, LOCK_EX | LOCK_NB) != 0)
            fail(errno == EWOULDBLOCK ? Code::busy : Code::io, "Profile already has a writer or cannot lock");
        return h;
    }
    void publish(const std::string& from, const std::string& to) const {
        check_file(from);
        if (::syscall(SYS_renameat2, handle.value, from.c_str(), handle.value, to.c_str(), RENAME_NOREPLACE) != 0)
            fail(errno == ENOSYS || errno == EINVAL || errno == EOPNOTSUPP ? Code::unsupported : Code::io,
                 "No-replace publication failed; source retained: " + from);
    }
    void sync() const {
        if (::fsync(handle.value) != 0) fail(Code::uncertain, "Directory flush failed; inspect published state");
    }
};
#endif

struct Entry {
    std::string name;
    std::string slot;
    std::uint64_t generation;
    std::string kind;
};
Entry parse_entry(const std::string& name) {
    const auto dot = name.find('.');
    if (dot == std::string::npos || name.size() < dot + 19 || name[dot + 17] != '.')
        fail(Code::unsafe_path, "Unknown profile entry retained: " + name);
    const auto slot = name.substr(0, dot);
    name_check(slot);
    std::uint64_t generation = 0;
    for (std::size_t i = dot + 1; i < dot + 17; ++i) {
        const char c = name[i];
        const int v = c >= '0' && c <= '9' ? c - '0' : (c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1);
        if (v < 0) fail(Code::unsafe_path, "Noncanonical record generation");
        generation = (generation << 4) | static_cast<std::uint64_t>(v);
    }
    const auto kind = name.substr(dot + 18);
    if (!generation || (kind != "pending" && kind != "record" && kind != "rejected"))
        fail(Code::unsafe_path, "Unknown record type retained: " + name);
    return {name, slot, generation, kind};
}
std::string filename(const std::string& slot, std::uint64_t generation, const std::string& kind) {
    std::string digits(16, '0');
    for (std::size_t i = 16; i > 0; --i) { digits[i - 1] = "0123456789abcdef"[generation & 15]; generation >>= 4; }
    return slot + "." + digits + "." + kind;
}
constexpr std::array<std::uint8_t, 8> magic{'M','W','3','H','S','V','1',0};
constexpr std::size_t header_size = 88;
void put(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint64_t n, std::size_t count) {
    for (std::size_t i = 0; i < count; ++i) { bytes[offset + i] = static_cast<std::uint8_t>(n & 255); n >>= 8; }
}
std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t offset, std::size_t count) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < count; ++i) value |= static_cast<std::uint64_t>(bytes[offset + i]) << (8 * i);
    return value;
}
std::uint32_t checksum(std::span<const std::uint8_t> bytes) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        if (i >= 84 && i < 88) continue;
        crc ^= bytes[i];
        for (unsigned bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320U : 0U);
    }
    return crc ^ 0xffffffffU;
}
std::vector<std::uint8_t> envelope(const std::string& profile, const std::string& slot,
                                   std::uint64_t generation, std::span<const std::uint8_t> payload) {
    std::vector<std::uint8_t> result(header_size + payload.size(), 0);
    std::copy(magic.begin(), magic.end(), result.begin());
    std::copy(profile.begin(), profile.end(), result.begin() + 8);
    std::copy(slot.begin(), slot.end(), result.begin() + 40);
    put(result, 72, generation, 8);
    put(result, 80, payload.size(), 4);
    std::copy(payload.begin(), payload.end(), result.begin() + header_size);
    put(result, 84, checksum(result), 4);
    return result;
}
std::vector<std::uint8_t> decode(const Directory& dir, const Entry& entry, const std::string& profile) {
    auto bytes = dir.read(entry.name, header_size + Profile::max_payload);
    if (bytes.size() < header_size || !std::equal(magic.begin(), magic.end(), bytes.begin()) ||
        get(bytes, 72, 8) != entry.generation || get(bytes, 80, 4) != bytes.size() - header_size ||
        get(bytes, 84, 4) != checksum(bytes)) fail(Code::corrupt, "Invalid host envelope: " + entry.name);
    const auto padded = [&](std::size_t offset, const std::string& expected) {
        return std::equal(expected.begin(), expected.end(), bytes.begin() + static_cast<std::ptrdiff_t>(offset)) &&
            std::all_of(bytes.begin() + static_cast<std::ptrdiff_t>(offset + expected.size()),
                        bytes.begin() + static_cast<std::ptrdiff_t>(offset + 32), [](auto v) { return v == 0; });
    };
    if (!padded(8, profile) || !padded(40, entry.slot)) fail(Code::corrupt, "Envelope profile/slot crossing: " + entry.name);
    bytes.erase(bytes.begin(), bytes.begin() + header_size);
    return bytes;
}
} // namespace

Error::Error(Code code, const std::string& message) : std::runtime_error(message), code_(code) {}
struct Transaction::Data {
    std::shared_ptr<int> session;
    std::string slot;
    std::uint64_t generation;
    bool used = false;
};
Transaction::Transaction(std::unique_ptr<Data> data) : data_(std::move(data)) {}
Transaction::Transaction(Transaction&&) noexcept = default;
Transaction& Transaction::operator=(Transaction&&) noexcept = default;
Transaction::~Transaction() = default;

struct Profile::Impl {
    Directory base;
    Directory content;
    Directory dir;
    Handle lock;
    std::string id;
    std::shared_ptr<int> session = std::make_shared<int>(0);
    std::vector<Entry> entries() const {
        std::vector<Entry> result;
        for (const auto& name : dir.list()) {
            // The exclusive .lock cannot be reopened with Windows sharing rules.
            if (name == ".lock") continue;
            dir.check_file(name);
            if (name != ".owner") result.push_back(parse_entry(name));
        }
        std::sort(result.begin(), result.end(), [](const auto& a, const auto& b) { return a.generation > b.generation; });
        return result;
    }
    Transaction::Data& token(Transaction& t) const {
        if (!t.data_ || t.data_->session != session || t.data_->used)
            fail(Code::transaction, "Transaction is consumed or belongs to another profile session");
        return *t.data_;
    }
    ReadResult read(const std::string& slot, bool recover) {
        name_check(slot);
        ReadResult result;
        const auto all = entries();
        bool pending = false;
        for (const auto& e : all) {
            if (e.slot != slot) continue;
            if (e.kind == "rejected") { result.diagnostics.push_back("Retained: " + e.name); continue; }
            if (e.kind == "pending") {
                pending = true;
                result.diagnostics.push_back("Interrupted/uncommitted: " + e.name);
                if (recover) { dir.publish(e.name, filename(e.slot, e.generation, "rejected")); dir.sync(); }
            }
        }
        if (pending && !recover) { result.state = State::recovery_required; return result; }
        for (const auto& e : all) {
            if (e.slot != slot || e.kind != "record") continue;
            try {
                result.payload = decode(dir, e, id);
                result.generation = e.generation;
                result.state = State::ready;
                return result;
            } catch (const Error& error) {
                if (error.code() != Code::corrupt) throw;
                result.diagnostics.push_back(error.what());
                if (!recover) { result.state = State::recovery_required; return result; }
                dir.publish(e.name, filename(e.slot, e.generation, "rejected"));
                dir.sync();
            }
        }
        return result;
    }
};

Profile::Profile(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}
Profile::Profile(Profile&&) noexcept = default;
Profile& Profile::operator=(Profile&&) noexcept = default;
Profile::~Profile() = default;
Profile Profile::create(const std::filesystem::path& base, const std::filesystem::path& content, const std::string& id) {
    return acquire(base, content, id, true);
}
Profile Profile::open(const std::filesystem::path& base, const std::filesystem::path& content, const std::string& id) {
    return acquire(base, content, id, false);
}
Profile Profile::acquire(const std::filesystem::path& base, const std::filesystem::path& content,
                         const std::string& id, bool create) {
    name_check(id);
    auto p = std::make_unique<Impl>();
    p->base = Directory::root(base);
    p->content = Directory::root(content);
    const auto base_id = p->base.ancestry.back();
    const auto content_id = p->content.ancestry.back();
    if (std::find(p->base.ancestry.begin(), p->base.ancestry.end(), content_id) != p->base.ancestry.end() ||
        std::find(p->content.ancestry.begin(), p->content.ancestry.end(), base_id) != p->content.ancestry.end())
        fail(Code::unsafe_path, "Prepared content and writable roots must be disjoint by identity");
#ifndef _WIN32
    const auto owner = info(p->base.handle, true);
    if (owner.st_uid != ::geteuid() || (owner.st_mode & 0022) != 0)
        fail(Code::not_owned, "Writable base must be owned by this user without group/other write access");
#endif
    p->dir = p->base.child(id, create);
#ifndef _WIN32
    const auto profile_owner = info(p->dir.handle, true);
    if (profile_owner.st_uid != ::geteuid() || (profile_owner.st_mode & 0022) != 0)
        fail(Code::not_owned, "Profile directory must be privately owned");
#endif
    p->id = id;
    const std::string marker = "MW3-HOST-PROFILE-1\n" + id + "\n";
    if (create) {
        p->dir.write_new(".owner", std::span(reinterpret_cast<const std::uint8_t*>(marker.data()), marker.size()));
        p->dir.sync();
        p->base.sync();
    } else {
        const auto bytes = p->dir.read(".owner", 64);
        if (std::string(bytes.begin(), bytes.end()) != marker) fail(Code::not_owned, "Profile ownership marker mismatch");
    }
    p->lock = p->dir.lock();
    (void)p->entries();
    return Profile(std::move(p));
}
Transaction Profile::stage(const std::string& slot, std::span<const std::uint8_t> payload) {
    name_check(slot);
    if (payload.size() > max_payload) fail(Code::limit, "Payload exceeds the 1 MiB bound");
    if (impl_->read(slot, false).state == State::recovery_required)
        fail(Code::recovery_required, "Explicit recovery required before another save");
    const auto entries = impl_->entries();
    if (entries.size() + 2 >= max_entries) fail(Code::limit, "Profile history budget exhausted; no automatic pruning");
    std::uint64_t generation = 0;
    for (const auto& e : entries) if (e.slot == slot) generation = std::max(generation, e.generation);
    if (generation == std::numeric_limits<std::uint64_t>::max()) fail(Code::limit, "Generation counter exhausted");
    ++generation;
    const auto bytes = envelope(impl_->id, slot, generation, payload);
    impl_->dir.write_new(filename(slot, generation, "pending"), bytes);
    impl_->dir.sync();
    auto token = std::make_unique<Transaction::Data>();
    token->session = impl_->session;
    token->slot = slot;
    token->generation = generation;
    return Transaction(std::move(token));
}
void Profile::commit(Transaction& transaction) {
    auto& t = impl_->token(transaction);
    const auto from = filename(t.slot, t.generation, "pending");
    // Detect damage even when it occurred after staging and before publication.
    (void)decode(impl_->dir, {from, t.slot, t.generation, "pending"}, impl_->id);
    impl_->dir.publish(from, filename(t.slot, t.generation, "record"));
    t.used = true;
    impl_->dir.sync();
}
void Profile::rollback(Transaction& transaction) {
    auto& t = impl_->token(transaction);
    impl_->dir.publish(filename(t.slot, t.generation, "pending"), filename(t.slot, t.generation, "rejected"));
    t.used = true;
    impl_->dir.sync();
}
ReadResult Profile::load(const std::string& slot) const { return impl_->read(slot, false); }
ReadResult Profile::recover(const std::string& slot) { return impl_->read(slot, true); }

} // namespace mw3::storage
