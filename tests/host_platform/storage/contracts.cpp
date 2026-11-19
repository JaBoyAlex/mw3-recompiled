// SPDX-License-Identifier: GPL-3.0-only
#include "storage/profile/store.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <csignal>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

using namespace mw3::storage;
namespace fs = std::filesystem;
namespace {
const std::vector<std::uint8_t> old_data{'o','l','d'};
const std::vector<std::uint8_t> new_data{'n','e','w'};
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error("ASSERT: " + message);
}
template<class F> void rejects(Code code, F&& action) {
    try { action(); } catch (const Error& error) {
        require(error.code() == code, "wrong rejection category: " + std::string(error.what()));
        return;
    }
    throw std::runtime_error("ASSERT: expected rejection was accepted");
}
std::vector<std::uint8_t> read(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    require(in.good(), "fixture read");
    return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}
void write(const fs::path& path, const std::vector<std::uint8_t>& bytes) {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    out.close();
    require(!out.fail(), "fixture write");
}
std::string leaf(unsigned generation, const std::string& kind = "record") {
    std::string hex(16, '0');
    for (std::size_t i = 16; i > 0; --i) { hex[i - 1] = "0123456789abcdef"[generation & 15]; generation >>= 4; }
    return "save." + hex + "." + kind;
}
void owned(const fs::path& path) {
    fs::create_directories(path);
#ifndef _WIN32
    require(::chmod(path.c_str(), 0700) == 0, "private fixture permissions");
#endif
}
struct Fixture {
    fs::path root, base, content;
    explicit Fixture(const fs::path& r) : root(r), base(r / "profiles"), content(r / "content") {
        owned(base); owned(content);
        if (!fs::exists(content / "immutable-canary")) write(content / "immutable-canary", old_data);
    }
    Profile create(const std::string& id = "alice") const { return Profile::create(base, content, id); }
    Profile open(const std::string& id = "alice") const { return Profile::open(base, content, id); }
    fs::path record(unsigned n, const std::string& kind = "record", const std::string& id = "alice") const {
        return base / id / leaf(n, kind);
    }
    void content_unchanged() const { require(read(content / "immutable-canary") == old_data, "content was modified"); }
};
void save(Profile& p, const std::vector<std::uint8_t>& bytes = old_data) {
    auto t = p.stage("save", bytes); p.commit(t);
}
void normal(const fs::path& root) {
    Fixture f(root);
    {
        auto p = f.create();
        require(p.load("save").state == State::missing, "new slot is missing");
        save(p);
        auto r = p.load("save");
        require(r.state == State::ready && r.generation == 1 && r.payload == old_data, "first load");
        save(p, {});
        require(p.load("save").payload.empty(), "empty payload round trip");
        std::vector<std::uint8_t> maximum(Profile::max_payload);
        for (std::size_t i = 0; i < maximum.size(); ++i) maximum[i] = static_cast<std::uint8_t>(i % 251);
        save(p, maximum);
        require(p.load("save").payload == maximum, "maximum payload round trip");
        require(read(f.record(1)).size() == 91, "original generation retained");
    }
    require(f.open().load("save").generation == 3, "reopen latest");
    f.content_unchanged();
}
void names(const fs::path& root) {
    Fixture f(root);
    auto p = f.create();
    const std::vector<std::string> bad{"", ".", "..", "../alice", "/tmp", "Alice", "a b", "a.", "a ",
        "a:b", "a/b", "a\\b", "con", "nul", "prn", "aux", "com0", "com1", "lpt9", "_a", "-a",
        std::string(33, 'a'), std::string("a\0b", 3), "\xc3\xa9", "\xef\xbc\x81"};
    for (const auto& name : bad) {
        rejects(Code::invalid_name, [&] { (void)p.stage(name, old_data); });
        rejects(Code::invalid_name, [&] { (void)p.load(name); });
        rejects(Code::invalid_name, [&] { (void)f.create(name); });
    }
    auto t = p.stage("a-0_b", old_data); p.commit(t);
    require(p.load("a-0_b").payload == old_data, "canonical name accepted");
    require(fs::is_empty(f.base / "alice") == false, "profile intact");
}
void roots(const fs::path& root) {
    Fixture f(root);
    rejects(Code::unsafe_path, [&] { (void)Profile::create("relative", f.content, "alice"); });
    rejects(Code::unsafe_path, [&] { (void)Profile::create(f.base / ".." / "profiles", f.content, "alice"); });
    rejects(Code::unsafe_path, [&] { (void)Profile::create(f.base, f.base, "alice"); });
    rejects(Code::unsafe_path, [&] { (void)Profile::create(f.base, root, "alice"); });
    rejects(Code::unsafe_path, [&] { (void)Profile::create(root, f.content, "alice"); });
    require(fs::is_empty(f.base), "rejected roots create nothing");
#ifdef _WIN32
    std::array<wchar_t, 4096> short_path{};
    const auto count = GetShortPathNameW(f.base.c_str(), short_path.data(), static_cast<DWORD>(short_path.size()));
    require(count > 0 && count < short_path.size(), "query actual Windows alias");
    rejects(Code::unsafe_path, [&] { (void)Profile::create(f.base, short_path.data(), "alias"); });
#else
    fs::permissions(f.base, fs::perms::group_write, fs::perm_options::add);
    rejects(Code::not_owned, [&] { (void)f.create(); });
    fs::permissions(f.base, fs::perms::group_write, fs::perm_options::remove);
#endif
    f.content_unchanged();
}
void ownership(const fs::path& root) {
    Fixture f(root);
    owned(f.base / "original");
    write(f.base / "original" / "original-save", old_data);
    rejects(Code::not_owned, [&] { (void)f.create("original"); });
    require(read(f.base / "original" / "original-save") == old_data, "original save retained");
    {
        auto p = f.create(); save(p);
        rejects(Code::busy, [&] { (void)f.open(); });
        rejects(Code::not_owned, [&] { (void)f.create(); });
    }
    { auto p = f.open(); require(p.load("save").payload == old_data, "lock released on destruction"); }
    write(f.base / "alice" / ".owner", new_data);
    rejects(Code::not_owned, [&] { (void)f.open(); });
    require(read(f.record(1)).size() == 91, "bad marker never overwrites save");
}
void corruption(const fs::path& root) {
    const std::vector<std::string> cases{"truncated", "header", "payload", "oversized", "length", "partial"};
    for (const auto& which : cases) {
        Fixture f(root / which);
        auto a = f.create(); auto b = f.create("bob"); save(a); save(b, new_data); save(a, new_data);
        const auto original = read(f.record(1));
        auto damaged = read(f.record(2));
        if (which == "truncated") damaged.resize(30);
        if (which == "header") damaged[0] ^= 1;
        if (which == "payload") damaged.back() ^= 1;
        if (which == "oversized") damaged.resize(Profile::max_payload + 89, 0);
        if (which == "length") damaged[80] ^= 1;
        if (which == "partial") damaged.clear();
        write(f.record(2), damaged);
        require(a.load("save").state == State::recovery_required, "corruption must not silently fall back");
        rejects(Code::recovery_required, [&] { (void)a.stage("save", old_data); });
        const auto r = a.recover("save");
        require(r.state == State::ready && r.payload == old_data && r.generation == 1 && !r.diagnostics.empty(), "explicit recovery");
        require(read(f.record(2, "rejected")) == damaged, "damaged bytes retained exactly");
        require(read(f.record(1)) == original && b.load("save").payload == new_data, "prior and other profile preserved");
        save(a, new_data);
        require(a.load("save").generation == 3, "never reuse rejected generation");
        f.content_unchanged();
    }
    Fixture f(root / "staged-damage");
    auto p = f.create(); save(p);
    auto t = p.stage("save", new_data);
    auto damaged = read(f.record(2, "pending"));
    damaged.back() ^= 1;
    write(f.record(2, "pending"), damaged);
    rejects(Code::corrupt, [&] { p.commit(t); });
    require(!fs::exists(f.record(2)) && p.load("save").state == State::recovery_required,
            "damaged staged bytes cannot be published");
    require(p.recover("save").payload == old_data && read(f.record(2, "rejected")) == damaged,
            "damaged stage retained while prior recovers");
}
void rollback(const fs::path& root) {
    Fixture f(root);
    auto p = f.create(); save(p);
    auto t = p.stage("save", new_data);
    require(p.load("save").state == State::recovery_required, "staged slot requires explicit action");
    p.rollback(t);
    require(p.load("save").payload == old_data && fs::exists(f.record(2, "rejected")), "rollback retained data and prior");
    rejects(Code::transaction, [&] { p.commit(t); });
    rejects(Code::transaction, [&] { p.rollback(t); });
    auto u = p.stage("save", new_data);
    auto moved = std::move(u);
    rejects(Code::transaction, [&] { p.commit(u); });
    p.commit(moved);
    rejects(Code::transaction, [&] { p.commit(moved); });
    require(p.load("save").generation == 3, "consumed/moved token handling");
    { auto abandoned = p.stage("save", old_data); (void)abandoned; }
    require(p.recover("save").payload == new_data && fs::exists(f.record(4, "rejected")), "abandoned token never promotes");
}
void crossing(const fs::path& root) {
    Fixture f(root);
    auto a = f.create(); auto b = f.create("bob");
    save(a); save(b);
    auto t = a.stage("save", new_data);
    rejects(Code::transaction, [&] { b.commit(t); });
    rejects(Code::transaction, [&] { b.rollback(t); });
    a.commit(t);
    save(b, new_data);
    fs::copy_file(f.record(2), f.record(2, "record", "bob"), fs::copy_options::overwrite_existing);
    require(b.load("save").state == State::recovery_required, "valid CRC cannot cross profile identity");
    require(b.recover("save").payload == old_data, "cross-profile copy quarantined");
    fs::copy_file(f.record(2), f.base / "alice" / "other.0000000000000002.record");
    require(a.load("other").state == State::recovery_required, "valid CRC cannot cross slot identity");
    require(a.recover("other").state == State::missing && a.load("save").payload == new_data, "slot isolation");
    Fixture g(root / "session");
    auto stale = [&] { auto p = g.create(); return p.stage("save", old_data); }();
    auto reopened = g.open();
    rejects(Code::transaction, [&] { reopened.commit(stale); });
    require(reopened.recover("save").state == State::missing, "session cannot reuse old token");
}
void publication(const fs::path& root) {
    Fixture f(root);
    auto p = f.create(); save(p);
    const auto old = read(f.record(1));
    auto t = p.stage("save", new_data);
    write(f.record(2), old_data); // actual conflicting target; never replaced
    rejects(Code::io, [&] { p.commit(t); });
    require(read(f.record(2)) == old_data && fs::exists(f.record(2, "pending")), "no-replace publication");
    p.rollback(t);
    rejects(Code::io, [&] { (void)p.recover("save"); });
    require(read(f.record(1)) == old && read(f.record(2)) == old_data &&
            fs::exists(f.record(2, "rejected")), "quarantine conflict preserves all evidence");
}
void limits(const fs::path& root) {
    Fixture f(root);
    auto p = f.create(); save(p);
    rejects(Code::limit, [&] { (void)p.stage("save", std::vector<std::uint8_t>(Profile::max_payload + 1)); });
    for (unsigned i = 2; i <= 254; ++i) write(f.record(i, "rejected"), {});
    rejects(Code::limit, [&] { (void)p.stage("save", new_data); });
    require(p.load("save").payload == old_data, "bounded full history preserves valid state");
    write(f.record(255, "rejected"), {});
    rejects(Code::limit, [&] { (void)p.load("save"); });
    Fixture g(root / "overflow");
    auto q = g.create(); save(q);
    write(g.base / "alice" / "save.ffffffffffffffff.rejected", {});
    rejects(Code::limit, [&] { (void)q.stage("save", new_data); });
}
std::uint64_t resources_now() {
#ifdef _WIN32
    DWORD count = 0;
    require(GetProcessHandleCount(GetCurrentProcess(), &count) != 0, "handle count");
    return count;
#else
    return static_cast<std::uint64_t>(std::distance(fs::directory_iterator("/proc/self/fd"), fs::directory_iterator{}));
#endif
}
void resources(const fs::path& root) {
    Fixture f(root);
    { auto p = f.create(); save(p); }
    const auto before = resources_now();
    for (int i = 0; i < 128; ++i) {
        auto p = f.open();
        rejects(Code::busy, [&] { (void)f.open(); });
        require(p.load("save").payload == old_data, "repeated load");
        rejects(Code::unsafe_path, [&] { (void)Profile::open(f.base, f.base, "alice"); });
    }
    require(resources_now() == before, "native handles/fds leaked");
#ifndef _WIN32
    // Real bounded partial-write failure in this test process only. Restore the
    // soft limit and signal handler before recovery; no disk-filling fixture.
    auto p = f.open();
    struct rlimit original{};
    require(::getrlimit(RLIMIT_FSIZE, &original) == 0, "query file-size resource limit");
    auto bounded = original;
    bounded.rlim_cur = 90; // A three-byte payload needs 91 envelope bytes.
    const auto previous_signal = std::signal(SIGXFSZ, SIG_IGN);
    require(previous_signal != SIG_ERR, "ignore only this process file-size signal");
    require(::setrlimit(RLIMIT_FSIZE, &bounded) == 0, "set private process write budget");
    try {
        rejects(Code::io, [&] { (void)p.stage("save", new_data); });
    } catch (...) {
        (void)::setrlimit(RLIMIT_FSIZE, &original);
        (void)std::signal(SIGXFSZ, previous_signal);
        throw;
    }
    require(::setrlimit(RLIMIT_FSIZE, &original) == 0, "restore file-size limit");
    (void)std::signal(SIGXFSZ, previous_signal);
    require(fs::file_size(f.record(2, "pending")) == 90, "actual partial write retained");
    require(p.load("save").state == State::recovery_required && p.recover("save").payload == old_data,
            "resource failure preserves previous committed payload");
    require(fs::file_size(f.record(2, "rejected")) == 90, "partial resource-failure diagnostic retained");
#endif
}
void links(const fs::path& root) {
    Fixture f(root);
    const auto outside = root / "outside";
    owned(outside); write(outside / "canary", old_data);
    {
        auto p = f.create(); save(p);
        fs::create_hard_link(outside / "canary", f.record(2));
        rejects(Code::unsafe_path, [&] { (void)p.load("save"); });
        rejects(Code::unsafe_path, [&] { (void)p.recover("save"); });
        require(read(outside / "canary") == old_data && read(f.record(1)).size() == 91, "hard-link canary/prior intact");
    }
    for (const auto& internal : {".owner", ".lock"}) {
        Fixture g(root / (std::string("internal-") + internal));
        { auto p = g.create(); save(p); }
        require(fs::remove(g.base / "alice" / internal), "remove only private fixture internal file");
        fs::create_hard_link(outside / "canary", g.base / "alice" / internal);
        rejects(Code::unsafe_path, [&] { (void)g.open(); });
        require(read(g.record(1)).size() == 91, "internal hard-link prior intact");
    }
    std::error_code ec;
    fs::create_directory_symlink(outside, root / "redirect", ec);
    if (ec) {
#ifdef _WIN32
        require(ec.value() == ERROR_PRIVILEGE_NOT_HELD, "unexpected symlink creation failure: " + ec.message());
        std::cout << "SKIP: Windows symlink privilege unavailable; junction tested by Python driver\n";
#else
        throw std::runtime_error("real symlink fixture failed: " + ec.message());
#endif
    } else {
        rejects(Code::unsafe_path, [&] { (void)Profile::create(root / "redirect", f.content, "x"); });
        Fixture g(root / "file-link");
        auto p = g.create(); save(p);
        fs::create_symlink(outside / "canary", g.record(2));
        rejects(Code::unsafe_path, [&] { (void)p.load("save"); });
        rejects(Code::unsafe_path, [&] { (void)p.recover("save"); });
        require(read(g.record(1)).size() == 91, "symlink prior intact");
    }
    require(read(outside / "canary") == old_data, "link canary unchanged");
    f.content_unchanged();
}
void measure(const fs::path& root, int warmup) {
    Fixture f(root);
    auto p = f.create();
    const std::vector<std::uint8_t> payload(64 * 1024, 0x5a);
    // Include append-only history cost; never benchmark by omitting durability.
    for (int i = 0; i < warmup; ++i) save(p, payload);
    std::vector<double> timings;
    for (int i = 0; i < 24; ++i) {
        const auto begin = std::chrono::steady_clock::now();
        save(p, payload);
        require(p.load("save").payload == payload, "benchmark must retain correctness");
        timings.push_back(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - begin).count());
    }
    std::cout << "SYNTHETIC samples_ms=";
    for (const auto ms : timings) std::cout << ms << ',';
    std::cout << '\n';
    std::sort(timings.begin(), timings.end());
    std::cout << "SYNTHETIC 64KiB stage+commit+load ms median=" << (timings[11] + timings[12]) / 2.0
              << " p95=" << timings[22] << " max=" << timings.back() << " count=24 warmup=" << warmup << '\n';
}
void benchmark(const fs::path& root) { measure(root, 3); }
void benchmark_history(const fs::path& root) { measure(root, 200); }

// Child modes use a caller-owned existing synthetic tree. No automatic cleanup,
// no process discovery, no game input; the Python parent owns lifecycle/timeout.
void child(const std::string& mode, const fs::path& root) {
    Fixture f(root);
    if (mode == "init") { auto p = f.create(); save(p); }
    else if (mode == "pending-exit") {
        auto p = f.open(); auto t = p.stage("save", new_data); (void)t;
        std::_Exit(71);
    } else if (mode == "commit-exit") {
        auto p = f.open(); save(p, new_data); std::_Exit(72);
    } else if (mode == "recover") {
        auto p = f.open();
        require(p.load("save").state == State::recovery_required, "crashed pending detected");
        require(p.recover("save").payload == old_data, "explicit process recovery keeps prior");
        require(fs::exists(f.record(2, "rejected")), "crashed pending retained");
    } else if (mode == "expect-new") {
        require(f.open().load("save").payload == new_data, "committed process exit persists new payload");
    } else if (mode == "wrong-expectation") {
        require(f.open().load("save").payload == new_data, "negative detector wrong payload");
    } else if (mode == "busy") {
        rejects(Code::busy, [&] { (void)f.open(); });
    } else if (mode == "hold") {
        auto p = f.open();
        std::cout << "READY\n" << std::flush;
        std::string line; std::getline(std::cin, line);
        require(line == "release", "parent lock-release protocol");
    } else if (mode == "open") {
        require(f.open().load("save").state == State::ready, "open after owner exit");
    } else if (mode == "unsafe-root") {
        rejects(Code::unsafe_path, [&] { (void)Profile::create(root / "redirect", f.content, "alice"); });
    } else if (mode == "unsafe-entry") {
        rejects(Code::unsafe_path, [&] { (void)f.open(); });
    } else throw std::invalid_argument("unknown child mode");
    f.content_unchanged();
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: profile-tests CASE PRIVATE-PARENT\n"; return 2; }
    const std::string which(argv[1]);
    const fs::path parent = fs::absolute(argv[2]);
    try {
        if (which.starts_with("child-")) child(which.substr(6), parent);
        else {
            const std::vector<std::pair<std::string, std::function<void(const fs::path&)>>> cases{
                {"normal", normal}, {"names", names}, {"roots", roots}, {"ownership", ownership},
                {"corruption", corruption}, {"rollback", rollback}, {"crossing", crossing},
                {"publication", publication}, {"limits", limits}, {"resources", resources}, {"links", links},
                {"benchmark", benchmark}, {"benchmark-history", benchmark_history}};
            const auto it = std::find_if(cases.begin(), cases.end(), [&](const auto& c) { return c.first == which; });
            if (it == cases.end()) { std::cerr << "unknown case\n"; return 2; }
            owned(parent);
            const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
            const auto root = parent / (which + "-" + std::to_string(nonce));
            require(fs::create_directory(root), "fresh exclusive fixture root");
            it->second(root);
        }
        std::cout << "PASS: host-profile " << which << "; MW3 save/load NOT TESTED\n";
        return 0;
    } catch (const std::invalid_argument& e) {
        std::cerr << "INVALID: " << e.what() << '\n'; return 2;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << which << ": " << e.what() << " (fixtures retained under " << parent.string() << ")\n";
        return 1;
    }
}
