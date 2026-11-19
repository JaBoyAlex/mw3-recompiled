// SPDX-License-Identifier: GPL-3.0-only
// Original game-free diagnostics; imports the actual SDK filesystem module.
#include <rex/app/app.h>
#include <rex/filesystem/file_system_factory.h>
#include <rex/platform/thread.h>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#if defined(_WIN32)
#include <windows.h>
#include <winioctl.h>
#else
#include <dlfcn.h>
#endif

namespace {
namespace fs = std::filesystem;
namespace vfs = rex::filesystem;
using rex::u8;
struct ContractApp : rex::app::App {
  ContractApp() : App("mw3_profile_storage") {}
  rex::AppSysRequirements GetRequirements() const override { return {}; }
};
void Require(bool value, const char* reason) {
  if (!value) throw std::runtime_error(reason);
}
std::string ReadHost(const fs::path& path) {
  std::ifstream stream(path, std::ios::binary);
  Require(bool(stream), "host-canary-unreadable");
  return {std::istreambuf_iterator<char>(stream), {}};
}
void WriteHost(const fs::path& path, std::string_view bytes) {
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  Require(bool(stream), "fixture-create-failed");
  stream.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
  stream.close();
  Require(!stream.fail(), "fixture-write-failed");
}
std::string Read(vfs::IFile& file) {
  // The SDK explicitly caches node metadata; refresh before observing a write.
  file.Refresh();
  const auto size = file.GetInfo().size;
  Require(size <= 4096, "fixture-read-not-bounded");
  std::array<u8, 4096> buffer{};
  auto result = file.Read(std::span(buffer).first(static_cast<size_t>(size)), 0);
  Require(bool(result) && *result == size, "short-or-failed-read");
  return {reinterpret_cast<const char*>(buffer.data()), static_cast<size_t>(size)};
}
vfs::Opened Open(vfs::IFileSystem& files, std::string_view path,
                 vfs::OpenOptions options = {}) {
  auto opened = files.Open(path, options);
  Require(bool(opened), "expected-open-failed");
  return std::move(*opened);
}
vfs::OpenOptions WriteOptions(vfs::Disposition disposition = vfs::Disposition::kOpen) {
  return {disposition, vfs::Access::kReadAccess | vfs::Access::kWriteAccess, false, true};
}
void Write(vfs::IFile& file, std::string_view bytes) {
  auto result = file.Write(std::span(reinterpret_cast<const u8*>(bytes.data()), bytes.size()), 0);
  Require(bool(result) && *result == bytes.size(), "short-or-failed-write");
  Require(bool(file.Flush()), "flush-failed");
}
struct Fixture {
  fs::path root;
  vfs::IFileSystemFactory& factory;
  Fixture(fs::path directory, vfs::IFileSystemFactory& source)
      : root(std::move(directory)), factory(source) {
    Require(fs::create_directory(root), "fixture-directory-not-exclusive");
    for (const char* name : {"a", "b", "content", "outside"})
      Require(fs::create_directory(root / name), "fixture-subdirectory-not-exclusive");
    WriteHost(root / "a/session.dat", "PROFILE_A");
    WriteHost(root / "b/session.dat", "PROFILE_B");
    WriteHost(root / "content/asset.dat", "CONTENT");
    WriteHost(root / "outside/canary.dat", "CANARY_ONLY");
  }
  std::unique_ptr<vfs::IFileSystem> Mount(const char* profile = "a") {
    auto files = factory.Create();
    Require(bool(files), "factory-returned-null");
    Require(bool(files->Mount({"\\Profile", vfs::ProviderType::kHostDirectory, root / profile,
                               vfs::MountFlags::kWritable, {}})), "profile-mount-failed");
    Require(bool(files->Mount({"\\Content", vfs::ProviderType::kHostDirectory, root / "content",
                               vfs::MountFlags::kNone, {}})), "content-mount-failed");
    return files;
  }
  void Canaries() {
    Require(ReadHost(root / "b/session.dat") == "PROFILE_B", "other-profile-changed");
    Require(ReadHost(root / "content/asset.dat") == "CONTENT", "read-only-content-changed");
    Require(ReadHost(root / "outside/canary.dat") == "CANARY_ONLY", "outside-canary-changed");
  }
};
void Profile(Fixture& f, bool mutation) {
  auto a = f.Mount(), b = f.Mount("b");
  auto first = Open(*a, "\\Profile\\session.dat");
  const auto actual = Read(*first.file);
  if (mutation) {
    std::fprintf(stderr, "MW3_STORAGE_MUTATION:wrong-profile\n");
    Require(actual == "WRONG_PROFILE", "deliberate-wrong-profile");
  }
  Require(actual == "PROFILE_A", "wrong-profile-a");
  auto second = Open(*b, "\\Profile\\session.dat");
  Require(Read(*second.file) == "PROFILE_B", "wrong-profile-b");
  first.file.reset();
  auto writer = Open(*a, "\\Profile\\session.dat", WriteOptions());
  Write(*writer.file, "UPDATED_A");
  writer.file.reset();
  a.reset();
  a = f.Mount();
  first = Open(*a, "\\Profile\\session.dat");
  Require(Read(*first.file) == "UPDATED_A", "profile-did-not-persist");
  Require(Read(*second.file) == "PROFILE_B", "profiles-not-independent");
  f.Canaries();
}
void ReadOnly(Fixture& f) {
  auto files = f.Mount();
  auto opened = files->Open("\\Content\\asset.dat", WriteOptions());
  if (opened) {
    const std::array<u8, 1> patch{'X'};
    Require(!opened->file->Write(patch, 0), "read-only-write-succeeded");
    Require(!opened->file->SetLength(0), "read-only-truncate-succeeded");
  }
  Require(!files->Open("\\Content\\new.dat", WriteOptions(vfs::Disposition::kCreate)),
          "read-only-create-succeeded");
  Require(!files->Open("\\Content\\asset.dat", WriteOptions(vfs::Disposition::kOverwrite)),
          "read-only-overwrite-succeeded");
  Require(!files->CreateDirectories("\\Content\\newdir"), "read-only-mkdir-succeeded");
  Require(!files->Remove("\\Content\\asset.dat"), "read-only-remove-succeeded");
  Require(!files->Rename("\\Content\\asset.dat", "\\Profile\\stolen.dat", false),
          "read-only-rename-succeeded");
  f.Canaries();
}
void Bounds(Fixture& f) {
  auto files = f.Mount();
  for (const auto* path : {"\\Profile\\..\\outside\\canary.dat",
       "\\Profile\\sub\\..\\..\\outside\\canary.dat", "\\ProfileEvil\\session.dat",
       "\\Profile\\bad:name", "\\Profile\\../../outside/canary.dat"}) {
    Require(!files->Open(path, {}), "out-of-root-open-succeeded");
    Require(!files->Open(path, WriteOptions(vfs::Disposition::kCreate)), "out-of-root-create-succeeded");
  }
  const std::string nul("\\Profile\\session.dat\0suffix", 27);
  Require(!files->Open(nul, {}), "nul-path-accepted");
  f.Canaries();
}
void Relative(Fixture& f) {
  auto files = f.Mount();
  Require(bool(files->CreateDirectories("\\Profile\\sub")), "relative-directory-create-failed");
  auto root = Open(*files, "\\Profile\\sub");
  auto child = files->OpenRelative(*root.file, "new.dat", WriteOptions(vfs::Disposition::kCreate));
  Require(bool(child), "relative-create-failed");
  Write(*child->file, "RELATIVE");
  child->file.reset();
  child = files->OpenRelative(*root.file, "new.dat", {});
  Require(bool(child) && Read(*child->file) == "RELATIVE", "relative-payload-mismatch");
  Require(!files->OpenRelative(*root.file, "../../outside/canary.dat", {}), "relative-escape-succeeded");
  f.Canaries();
}
void RenameRemove(Fixture& f) {
  auto files = f.Mount();
  auto created = Open(*files, "\\Profile\\pending.dat", WriteOptions(vfs::Disposition::kCreate));
  Write(*created.file, "COMMITTED");
  created.file.reset();
  Require(bool(files->Rename("\\Profile\\pending.dat", "\\Profile\\ready.dat", false)), "rename-failed");
  Require(!files->Stat("\\Profile\\pending.dat"), "rename-source-retained");
  auto read = Open(*files, "\\Profile\\ready.dat");
  Require(Read(*read.file) == "COMMITTED", "renamed-payload-mismatch");
  read.file.reset();
  Require(!files->Rename("\\Profile\\ready.dat", "\\Content\\replace.dat", false), "cross-mount-rename-succeeded");
  Require(!files->Remove("\\Profile"), "mount-root-remove-succeeded");
  Require(bool(files->Remove("\\Profile\\ready.dat")), "remove-failed");
  Require(!files->Stat("\\Profile\\ready.dat"), "removed-file-retained");
  f.Canaries();
}
bool Junction(const fs::path& link, const fs::path& target) {
#if defined(_WIN32)
  // Bounded IO_REPARSE_TAG_MOUNT_POINT buffer; only new private fixture paths.
  // Layout: Microsoft's REPARSE_DATA_BUFFER / MountPointReparseBuffer contract.
  struct Buffer {
    DWORD tag;
    WORD length, reserved, substitute_offset, substitute_length, print_offset, print_length;
    wchar_t paths[2048];
  } buffer{};
  const std::wstring printable = fs::absolute(target).wstring();
  const std::wstring substitute = L"\\??\\" + printable;
  Require(printable.size() + substitute.size() + 2 < std::size(buffer.paths), "junction-path-too-long");
  buffer.tag = IO_REPARSE_TAG_MOUNT_POINT;
  buffer.substitute_length = static_cast<WORD>(substitute.size() * sizeof(wchar_t));
  buffer.print_offset = static_cast<WORD>((substitute.size() + 1) * sizeof(wchar_t));
  buffer.print_length = static_cast<WORD>(printable.size() * sizeof(wchar_t));
  buffer.length = static_cast<WORD>(8 + (substitute.size() + printable.size() + 2) * sizeof(wchar_t));
  std::memcpy(buffer.paths, substitute.c_str(), buffer.substitute_length);
  std::memcpy(buffer.paths + substitute.size() + 1, printable.c_str(), buffer.print_length);
  Require(fs::create_directory(link), "junction-directory-not-exclusive");
  HANDLE handle = CreateFileW(link.c_str(), GENERIC_WRITE, 0, nullptr, OPEN_EXISTING,
                              FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  Require(handle != INVALID_HANDLE_VALUE, "junction-handle-open-failed");
  DWORD returned = 0;
  const BOOL set = DeviceIoControl(handle, FSCTL_SET_REPARSE_POINT, &buffer, 8 + buffer.length,
                                    nullptr, 0, &returned, nullptr);
  const DWORD error = set ? ERROR_SUCCESS : GetLastError();
  Require(CloseHandle(handle) != 0, "junction-handle-close-failed");
  if (!set) {
    if (error == ERROR_PRIVILEGE_NOT_HELD || error == ERROR_NOT_SUPPORTED) return false;
    throw std::runtime_error("junction-reparse-creation-failed");
  }
  return true;
#else
  (void)link;
  (void)target;
  return false;
#endif
}
bool Link(Fixture& f, bool directory, bool junction = false) {
  std::error_code error;
  const auto link = f.root / "a/redirect";
  if (junction) {
    if (!Junction(link, f.root / "outside")) return false;
  } else if (directory) fs::create_directory_symlink(f.root / "outside", link, error);
  else fs::create_symlink(f.root / "outside/canary.dat", link, error);
  if (error) {
    if (error == std::errc::permission_denied || error == std::errc::operation_not_permitted ||
        error == std::errc::function_not_supported) return false;
#if defined(_WIN32)
    if (error.value() == ERROR_PRIVILEGE_NOT_HELD) return false;
#endif
    throw std::runtime_error("link-fixture-creation-failed");
  }
  auto files = f.Mount();
  auto opened = files->Open(directory ? "\\Profile\\redirect\\canary.dat" : "\\Profile\\redirect",
                            directory ? WriteOptions() : vfs::OpenOptions{});
  bool read_outside = false, wrote_outside = false;
  if (opened) {
    read_outside = Read(*opened->file) == "CANARY_ONLY";
    if (directory) {
      const std::array<u8, 1> patch{'X'};
      auto written = opened->file->Write(patch, 0);
      wrote_outside = written && *written == 1;
      if (written) Require(bool(opened->file->Flush()), "escape-write-flush-failed");
    }
  }
  const bool changed = ReadHost(f.root / "outside/canary.dat") != "CANARY_ONLY";
  std::fprintf(stderr, "MW3_STORAGE_LINK:directory=%d opened=%d read_outside=%d wrote_outside=%d changed=%d\n",
               directory, bool(opened), read_outside, wrote_outside, changed);
  Require(!opened && !read_outside && !wrote_outside && !changed, "host-link-crossed-profile-root");
  f.Canaries();
  return true;
}
void Library(vfs::IFileSystemFactory* factory) {
  // Locate a real virtual method in the factory's dynamically loaded module.
  const void* table = nullptr;
  const void* method = nullptr;
  std::memcpy(&table, factory, sizeof(table));
  std::memcpy(&method, table, sizeof(method));
#if defined(_WIN32)
  HMODULE module = nullptr;
  Require(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(method), &module) != 0, "module-address-unresolved");
  std::array<wchar_t, 32768> path{};
  auto length = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
  Require(length && length < path.size(), "module-path-unresolved");
  std::fprintf(stderr, "MW3_STORAGE_LIBRARY:%s\n", fs::path(path.data()).string().c_str());
#else
  Dl_info info{};
  Require(dladdr(method, &info) && info.dli_fname, "module-path-unresolved");
  std::fprintf(stderr, "MW3_STORAGE_LIBRARY:%s\n", info.dli_fname);
#endif
}
int Run(ContractApp& app, const rex::CLIArgList& args) {
  const auto before = rex::platform::detail::GetThreadCount();
  const char* root_value = std::getenv("MW3_STORAGE_TREE");
  const char* mode_value = std::getenv("MW3_STORAGE_CASES");
  if (!root_value || !mode_value) return 2;
  const fs::path root(root_value);
  const std::string mode(mode_value);
  if (ReadHost(root / ".owner") != "mw3-profile-storage-v1") return 2;
  if (!app.Init(args)) return 2;
  unsigned count = 0, failures = 0, skips = 0;
  try {
    auto* factory = REX_INTERFACE(vfs::IFileSystemFactory);
    Require(factory != nullptr, "filesystem-factory-unavailable");
    Library(factory);
    if (mode == "incomplete") {
      Require(app.Shutdown() == 0, "app-shutdown-failed");
      std::fprintf(stderr, "MW3_STORAGE_INCOMPLETE:armed\n");
      return 43;
    }
    size_t begin = 0;
    while (begin < mode.size()) {
      const auto end = mode.find(',', begin);
      const std::string selected = mode.substr(begin, end == std::string::npos ? end : end - begin);
      Require(count < 32, "too-many-cases");
      const auto started = std::chrono::steady_clock::now();
      const char* status = "PASS";
      try {
        Fixture f(root / std::to_string(count), *factory);
        const bool mutation = std::getenv("MW3_STORAGE_MUTATION") != nullptr;
        if (selected == "profiles") Profile(f, mutation);
        else if (selected == "read-only") ReadOnly(f);
        else if (selected == "bounds") Bounds(f);
        else if (selected == "relative") Relative(f);
        else if (selected == "rename-remove") RenameRemove(f);
        else if (selected == "file-link" || selected == "directory-link" || selected == "directory-junction") {
          if (!Link(f, selected != "file-link", selected == "directory-junction")) {
            status = "SKIP";
            ++skips;
            std::fprintf(stderr, "MW3_STORAGE_SKIP:case=%s reason=host-link-permission-or-unsupported\n", selected.c_str());
          }
        } else throw std::runtime_error("unknown-case");
      } catch (const std::exception& error) {
        ++failures;
        status = "FAIL";
        std::fprintf(stderr, "MW3_STORAGE_FAILURE:case=%s reason=%s\n", selected.c_str(), error.what());
      }
      ++count;
      const auto micros = std::chrono::duration_cast<std::chrono::microseconds>(
          std::chrono::steady_clock::now() - started).count();
      std::fprintf(stderr, "MW3_STORAGE_CASE:name=%s status=%s microseconds=%lld\n",
                   selected.c_str(), status, static_cast<long long>(micros));
      if (end == std::string::npos) break;
      begin = end + 1;
    }
    Require(app.Shutdown() == 0, "app-shutdown-failed");
    const auto after = rex::platform::detail::GetThreadCount();
    std::fprintf(stderr, "MW3_STORAGE_COMPLETE:count=%u failures=%u skips=%u threads_before=%llu threads_after=%llu\n",
                 count, failures, skips, static_cast<unsigned long long>(before), static_cast<unsigned long long>(after));
    return before == after ? (failures ? 42 : 0) : 2;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "MW3_STORAGE_FATAL:%s\n", error.what());
    app.Shutdown();
    return 2;
  }
}
}  // namespace
REX_CONSOLE_APP_MAIN(ContractApp, Run)
