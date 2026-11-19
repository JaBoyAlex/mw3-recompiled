// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic host GPU work on the unchanged SDK's actual D3D12 device.
#include "gpu/xenos/host/d3d12/d3d12_provider.h"
#include "gpu/xenos/xenos_graphics_driver_base.h"
#include <rex/driver_context.h>
#include <rex/driver_module.h>
#include <rex/gpu/graphics_system.h>
#include <rex/logging/logger.h>
#include <rex/settings_registry.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using Microsoft::WRL::ComPtr;
namespace {
using Clock = std::chrono::steady_clock;
std::uint64_t checks{};
void Check(bool value, const char* message) { ++checks; if (!value) throw std::runtime_error(message); }
void HR(HRESULT result, const char* message) { Check(SUCCEEDED(result), message); }
template<class T> void Ok(const T& result, const char* message) { Check(bool(result), message); }
std::uint64_t Elapsed(Clock::time_point start) {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count());
}
std::string Quote(std::string_view text) {
    std::string result = "\"";
    constexpr char digits[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') { result += '\\'; result += static_cast<char>(c); }
        else if (c < 32) { result += "\\u00"; result += digits[c >> 4]; result += digits[c & 15]; }
        else result += static_cast<char>(c);
    }
    return result + '"';
}
std::string UTF8(const wchar_t* text) {
    const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, -1, nullptr, 0, nullptr, nullptr);
    Check(size > 0, "adapter text conversion failed");
    std::string result(static_cast<std::size_t>(size), '\0');
    Check(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, -1, result.data(), size, nullptr, nullptr) == size,
          "adapter text conversion incomplete");
    result.pop_back(); return result;
}
std::string LoadedPath(const void* address) {
    HMODULE module{};
    Check(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(address), &module) != 0, "loaded module lookup failed");
    std::array<wchar_t, 32768> path{};
    const auto size = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
    Check(size > 0 && size < path.size(), "loaded module path truncated");
    return std::filesystem::path(path.data()).generic_string();
}
struct Library {
    HMODULE handle{};
    explicit Library(const std::filesystem::path& file) {
        handle = LoadLibraryExW(file.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        Check(handle != nullptr, "explicit actual SDK module could not load");
    }
    rex::CreateInterfaceFn Factory() const {
        auto result = reinterpret_cast<rex::CreateInterfaceFn>(GetProcAddress(handle, rex::kCreateInterfaceSymbol));
        Check(result != nullptr, "versioned SDK module factory missing"); return result;
    }
    void Close() {
        if (handle) { Check(FreeLibrary(handle) != 0, "owned SDK library reference release failed"); handle = nullptr; }
    }
    ~Library() { if (handle) FreeLibrary(handle); }
};
struct Diagnostics final : rex::log::ILogSink {
    std::atomic_uint64_t errors{}, warnings{};
    void Write(const rex::log::Message& message) override {
        if (message.level >= rex::log::Level::kError) ++errors;
        else if (message.level == rex::log::Level::kWarn) ++warnings;
    }
    void Flush() override {}
};
struct Dispatcher final : rex::IDriverContext {
    const std::thread::id owner = std::this_thread::get_id();
    std::vector<rex::MoveOnlyFunction<void()>> pending;
    rex::ISettingsRegistry& GetSettingsRegistry() override { return rex::GetSettingsRegistry(); }
    rex::ILogger& GetLogger() override { return rex::GetLogger(); }
    rex::Result<void> RunOnUIThread(rex::MoveOnlyFunction<void()> function) override {
        if (std::this_thread::get_id() != owner) return rex::Err(rex::ErrorCategory::kPlatform, "not the owned UI thread");
        function(); return rex::Ok();
    }
    void PostToUIThread(rex::MoveOnlyFunction<void()> function) override {
        Check(std::this_thread::get_id() == owner && pending.size() < 64, "UI queue ownership/budget violation");
        pending.push_back(std::move(function));
    }
    void Drain() {
        for (unsigned pass = 0; !pending.empty(); ++pass) {
            Check(pass < 64, "UI queue did not quiesce");
            auto work = std::move(pending); pending.clear(); for (auto& fn : work) fn();
        }
    }
};
struct Factory final : rex::IInterfaceFactory {
    rex::gpu::IGraphicsSystem* graphics{};
    rex::IInterface* Find(std::string_view name, u32 version) override {
        return name == rex::gpu::IGraphicsSystem::kInterface.name && version == rex::gpu::IGraphicsSystem::kInterface.version
            ? graphics : nullptr;
    }
    std::vector<rex::IInterface*> FindAll(std::string_view name, u32 version) override {
        auto* result = Find(name, version); return result ? std::vector<rex::IInterface*>{result} : std::vector<rex::IInterface*>{};
    }
};
struct Window {
    HWND handle{};
    Window() {
        handle = CreateWindowExW(0, L"STATIC", L"MW3 original private GPU diagnostic", WS_OVERLAPPED,
            0, 0, 256, 128, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
        Check(handle && !IsWindowVisible(handle), "owned hidden window creation failed");
    }
    void Close() {
        if (!handle) return;
        const auto previous = handle;
        Check(DestroyWindow(handle) != 0, "owned window cleanup failed"); handle = nullptr;
        Check(!IsWindow(previous), "owned window remained after cleanup");
    }
    ~Window() { if (handle) DestroyWindow(handle); }
};
struct Event {
    HANDLE handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    Event() { Check(handle != nullptr, "owned fence event creation failed"); }
    ~Event() { if (handle) CloseHandle(handle); }
};
struct Input { unsigned width{}, height{}; std::array<unsigned, 4> rgba{}; };
std::vector<Input> ReadInputs(const char* path) {
    std::ifstream file(path); Check(bool(file), "synthetic input file missing");
    std::vector<Input> result;
    for (std::string line; std::getline(file, line);) {
        std::istringstream row(line); Input value; std::string extra;
        Check(bool(row >> value.width >> value.height >> value.rgba[0] >> value.rgba[1] >> value.rgba[2] >> value.rgba[3]) &&
            !(row >> extra) && value.width > 0 && value.width <= 256 && value.height > 0 && value.height <= 128 &&
            std::all_of(value.rgba.begin(), value.rgba.end(), [](unsigned c) { return c <= 255; }), "invalid bounded synthetic input");
        Check(result.size() < 8, "too many synthetic inputs"); result.push_back(value);
    }
    Check(file.eof() && result.size() == 8, "incomplete synthetic inputs"); return result;
}
std::string Readback(ID3D12Device* device, ID3D12CommandQueue* queue, const Input& input, bool wrong) {
    D3D12_RESOURCE_DESC texture{};
    texture.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D; texture.Width = input.width; texture.Height = input.height;
    texture.DepthOrArraySize = 1; texture.MipLevels = 1; texture.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    texture.SampleDesc.Count = 1; texture.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    D3D12_HEAP_PROPERTIES heap{}; heap.Type = D3D12_HEAP_TYPE_DEFAULT;
    ComPtr<ID3D12Resource> target;
    HR(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &texture, D3D12_RESOURCE_STATE_RENDER_TARGET,
        nullptr, IID_PPV_ARGS(&target)), "original render target creation failed");
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{}; UINT rows{}; UINT64 row_bytes{}, total{};
    device->GetCopyableFootprints(&texture, 0, 1, 0, &footprint, &rows, &row_bytes, &total);
    Check(rows == input.height && row_bytes == input.width * 4 && footprint.Footprint.RowPitch >= row_bytes &&
          footprint.Offset <= total && total <= 1024 * 1024 &&
          footprint.Offset + (rows - 1) * static_cast<UINT64>(footprint.Footprint.RowPitch) + row_bytes <= total,
          "unexpected readback footprint");
    D3D12_RESOURCE_DESC buffer{}; buffer.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; buffer.Width = total;
    buffer.Height = 1; buffer.DepthOrArraySize = 1; buffer.MipLevels = 1; buffer.SampleDesc.Count = 1;
    buffer.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR; heap.Type = D3D12_HEAP_TYPE_READBACK;
    ComPtr<ID3D12Resource> readback;
    HR(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer, D3D12_RESOURCE_STATE_COPY_DEST,
        nullptr, IID_PPV_ARGS(&readback)), "readback resource creation failed");
    D3D12_DESCRIPTOR_HEAP_DESC descriptors{}; descriptors.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV; descriptors.NumDescriptors = 1;
    ComPtr<ID3D12DescriptorHeap> rtv;
    HR(device->CreateDescriptorHeap(&descriptors, IID_PPV_ARGS(&rtv)), "owned RTV heap creation failed");
    const auto view = rtv->GetCPUDescriptorHandleForHeapStart(); device->CreateRenderTargetView(target.Get(), nullptr, view);
    ComPtr<ID3D12CommandAllocator> allocator;
    HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)), "owned command allocator failed");
    ComPtr<ID3D12GraphicsCommandList> list;
    HR(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr, IID_PPV_ARGS(&list)), "owned command list failed");
    std::array<float, 4> color{};
    for (std::size_t i = 0; i < 4; ++i) color[i] = static_cast<float>(input.rgba[i]) / 255.0f;
    list->ClearRenderTargetView(view, color.data(), 0, nullptr);
    D3D12_RESOURCE_BARRIER barrier{}; barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = target.Get(); barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET; barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    list->ResourceBarrier(1, &barrier);
    D3D12_TEXTURE_COPY_LOCATION destination{}; destination.pResource = readback.Get();
    destination.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; destination.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION source{}; source.pResource = target.Get(); source.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    list->CopyTextureRegion(&destination, 0, 0, 0, &source, nullptr); HR(list->Close(), "owned command list close failed");
    ComPtr<ID3D12Fence> fence; HR(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)), "owned fence creation failed");
    Event event; ID3D12CommandList* commands[] = {list.Get()};
    const auto submitted = Clock::now(); queue->ExecuteCommandLists(1, commands);
    HR(queue->Signal(fence.Get(), 1), "owned queue fence signal failed");
    HR(fence->SetEventOnCompletion(1, event.handle), "owned fence notification failed");
    if (WaitForSingleObject(event.handle, 5000) != WAIT_OBJECT_0) {
        // Do not release in-flight resources and pretend orderly teardown succeeded.
        std::cerr << "MW3_GPU_FAILURE:GPU fence deadline; process cleanup required\n" << std::flush;
        std::_Exit(3);
    }
    const auto completion_ns = Elapsed(submitted);
    Check(fence->GetCompletedValue() == 1, "owned GPU fence did not complete exactly");
    HR(device->GetDeviceRemovedReason(), "GPU device removed");
    void* mapped{}; const D3D12_RANGE range{0, static_cast<SIZE_T>(total)};
    HR(readback->Map(0, &range, &mapped), "completed readback mapping failed");
    auto* bytes = static_cast<const unsigned char*>(mapped);
    std::uint64_t digest = 14695981039346656037ull; bool matches = true;
    for (unsigned y = 0; y < input.height; ++y) for (unsigned x = 0; x < input.width; ++x) for (unsigned c = 0; c < 4; ++c) {
        unsigned char actual = bytes[footprint.Offset + static_cast<UINT64>(y) * footprint.Footprint.RowPitch + x * 4 + c];
        // Detector control changes one CPU-side observation after actual GPU completion.
        if (wrong && y == 0 && x == 0 && c == 0) actual ^= 1;
        matches &= actual == input.rgba[c]; digest = (digest ^ actual) * 1099511628211ull;
    }
    const D3D12_RANGE written{0, 0}; readback->Unmap(0, &written);
    Check(matches, wrong ? "deliberate wrong-pixel rejected" : "synthetic pixel mismatch");
    std::ostringstream hash; hash << std::hex << std::setw(16) << std::setfill('0') << digest;
    std::ostringstream result;
    result << "{\"width\":" << input.width << ",\"height\":" << input.height << ",\"pixel_hash\":" << Quote(hash.str())
           << ",\"pixels\":" << input.width * input.height << ",\"row_pitch\":" << footprint.Footprint.RowPitch
           << ",\"fence\":1,\"completion_ns\":" << completion_ns << '}';
    return result.str();
}
} // namespace

int main(int argc, char** argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    if (argc != 7) { std::cerr << "MW3_GPU_FAILURE:arguments required\n"; return 2; }
    const std::string_view name = argv[1], nonce = argv[2], control = argv[6];
    if ((name != "bootstrap" && name != "lifetime" && name != "heldout") || nonce.size() != 32 ||
        !std::all_of(nonce.begin(), nonce.end(), [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
        (control != "ordinary" && control != "wrong-pixel" && control != "incomplete" && control != "deadline")) {
        std::cerr << "MW3_GPU_FAILURE:invalid case, nonce or control\n"; return 2;
    }
    try {
        const auto inputs = ReadInputs(argv[3]);
        Diagnostics diagnostics;
        const auto sink = rex::GetLogger().AddSink(diagnostics);
        const std::array<const rex::log::LogCategory*, 2> categories{&rex::log::gpu, &rex::log::ui};
        Ok(rex::GetLogger().AddCategories(categories), "GPU/UI diagnostic category registration failed");
        const rex::ScopeGuard remove_categories([&] { rex::GetLogger().RemoveCategories(categories); });
        Library graphics(argv[4]), provider(argv[5]);
        const auto make_graphics = graphics.Factory(), make_provider = provider.Factory();
        Factory factory;
        factory.graphics = static_cast<rex::gpu::IGraphicsSystem*>(make_graphics(
            rex::gpu::IGraphicsSystem::kInterface.name, rex::gpu::IGraphicsSystem::kInterface.version));
        auto* module = static_cast<rex::IModule*>(make_provider(rex::IModule::kInterface.name, rex::IModule::kInterface.version));
        auto* drivers = static_cast<rex::IDriverModule*>(make_provider(rex::IDriverModule::kInterface.name, rex::IDriverModule::kInterface.version));
        Check(factory.graphics && module && drivers && module->GetName() == "rexgpu-xenos-d3d12", "actual graphics interfaces missing");
        const std::string loaded = "{\"provider\":" + Quote(LoadedPath(reinterpret_cast<const void*>(make_provider))) +
            ",\"graphics\":" + Quote(LoadedPath(reinterpret_cast<const void*>(make_graphics))) +
            ",\"base\":" + Quote(LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger))) + '}';
        std::cout << "MW3_GPU_LIBRARIES:{\"nonce\":" << Quote(nonce) << ",\"loaded\":" << loaded << "}\n" << std::flush;
        ComPtr<ID3D12Debug> debug;
        const auto debug_hr = D3D12GetDebugInterface(IID_PPV_ARGS(&debug));
        const bool debug_enabled = SUCCEEDED(debug_hr);
        if (debug_enabled) debug->EnableDebugLayer();
        Ok(module->Connect(factory), "actual provider Connect failed");
        rex::ScopeGuard disconnect([&] { module->Disconnect(); });
        Ok(module->Init(), "actual provider Init failed");
        rex::ScopeGuard shutdown([&] { module->Shutdown(); });
        Check(drivers->GetDrivers().size() == 1, "unexpected graphics registrations");
        const auto& registration = drivers->GetDrivers().front();
        Check(registration.type == rex::DriverType::kGraphics && registration.family == rex::GraphicsFamily::kXenos &&
              registration.name == "d3d12" && registration.create, "explicit D3D12 driver absent");
        Dispatcher context;
        std::vector<std::string> records, devices;
        const unsigned cycles = name == "lifetime" ? 3 : 1;
        for (unsigned cycle = 0; cycle < cycles; ++cycle) {
            const auto start = Clock::now(); Window window;
            auto driver = registration.create(); Check(driver && driver->GetName() == "d3d12", "driver selection changed");
            Ok(driver->Initialize(context), "actual D3D12 Initialize failed");
            rex::ScopeGuard stop([&] { driver->Shutdown(); });
            auto* gpu = static_cast<rex::gpu::IGraphicsDriver*>(driver.get()); Check(gpu->AsXenos(), "unexpected native/null driver");
            auto& registry = context.GetSettingsRegistry();
            Ok(registry.SetText(rex::SettingLayer::kTitle, "gpu.d3d12.adapter", "-1"), "private adapter setting failed");
            rex::NativeWindow surface{}; surface.type = rex::NativeWindow::Type::kWin32; surface.window = window.handle;
            Ok(gpu->SetSurface(surface), "actual hidden surface creation failed");
            gpu->ResizeSurface(128, 64); Check(gpu->BeginPresent(), "actual hidden surface attachment failed"); gpu->EndPresent();
            const auto initialization_ns = Elapsed(start);
            // Diagnostic-only introspection is bound to the exact source/package ABI.
            auto* xenos = static_cast<rex::gpu::XenosGraphicsDriverBase*>(gpu->AsXenos());
            auto* d3d = static_cast<rex::gpu::d3d12::D3D12Provider*>(xenos->GetProvider());
            Check(d3d && d3d->GetDevice() && d3d->GetDirectQueue(), "actual SDK D3D12 device/queue absent");
            auto* device = d3d->GetDevice(); ComPtr<IDXGIFactory4> dxgi;
            HR(d3d->GetDXGIFactory()->QueryInterface(IID_PPV_ARGS(&dxgi)), "actual adapter factory unavailable");
            ComPtr<IDXGIAdapter1> adapter;
            const auto luid = device->GetAdapterLuid();
            HR(dxgi->EnumAdapterByLuid(luid, IID_PPV_ARGS(&adapter)), "actual device adapter lookup failed");
            DXGI_ADAPTER_DESC1 description{}; HR(adapter->GetDesc1(&description), "actual adapter identity unavailable");
            Check(!(description.Flags & DXGI_ADAPTER_FLAG_SOFTWARE), "software adapter is not an eligible hardware observation");
            LARGE_INTEGER version{}; const auto version_hr = adapter->CheckInterfaceSupport(__uuidof(IDXGIDevice), &version);
            std::ostringstream identity;
            identity << "{\"name\":" << Quote(UTF8(description.Description)) << ",\"vendor\":" << description.VendorId
                << ",\"device\":" << description.DeviceId << ",\"luid_low\":" << luid.LowPart << ",\"luid_high\":" << luid.HighPart
                << ",\"dedicated_bytes\":" << description.DedicatedVideoMemory << ",\"software\":false,\"driver_version\":"
                << (SUCCEEDED(version_hr) ? std::to_string(version.QuadPart) : "null") << ",\"driver_version_hresult\":"
                << static_cast<std::uint32_t>(version_hr) << ",\"initialization_ns\":" << initialization_ns << '}';
            devices.push_back(identity.str());
            for (const auto& input : inputs) records.push_back(Readback(device, d3d->GetDirectQueue(), input, control == "wrong-pixel"));
            std::uint64_t debug_warnings = 0;
            if (debug_enabled) {
                ComPtr<ID3D12InfoQueue> messages;
                HR(device->QueryInterface(IID_PPV_ARGS(&messages)), "enabled D3D12 debug queue absent");
                const auto count = messages->GetNumStoredMessagesAllowedByRetrievalFilter();
                Check(count < 4096, "debug message budget exceeded");
                for (UINT64 i = 0; i < count; ++i) {
                    SIZE_T size{}; HR(messages->GetMessage(i, nullptr, &size), "debug message length failed");
                    Check(size >= sizeof(D3D12_MESSAGE) && size < 1024 * 1024, "debug message length exceeds budget");
                    std::vector<std::uint64_t> storage((size + 7) / 8);
                    auto* message = reinterpret_cast<D3D12_MESSAGE*>(storage.data());
                    HR(messages->GetMessage(i, message, &size), "debug message retrieval failed");
                    Check(message->Severity != D3D12_MESSAGE_SEVERITY_CORRUPTION && message->Severity != D3D12_MESSAGE_SEVERITY_ERROR,
                          "D3D12 validation error");
                    if (message->Severity == D3D12_MESSAGE_SEVERITY_WARNING) {
                        ++debug_warnings;
                        std::cout << "MW3_GPU_DEBUG_WARNING:" << Quote(std::string_view(message->pDescription, message->DescriptionByteLength)) << '\n';
                    }
                }
            }
            const auto cleanup = Clock::now();
            stop.Reset(); driver.reset(); context.Drain(); window.Close();
            const auto cleanup_ns = Elapsed(cleanup);
            devices.back().pop_back(); devices.back() += ",\"cleanup_ns\":" + std::to_string(cleanup_ns) +
                ",\"debug_warnings\":" + std::to_string(debug_warnings) + '}';
        }
        shutdown.Reset(); disconnect.Reset();
        provider.Close(); graphics.Close();
        Check(context.pending.empty(), "owned UI queue not empty after cleanup");
        Check(diagnostics.errors.load() == 0, "actual SDK logged an error including teardown");
        std::cout << "MW3_GPU_READY:" << nonce << '\n' << std::flush;
        if (control == "incomplete") return 0;
        std::cout << "MW3_GPU_COMPLETE:{\"schema\":1,\"case\":" << Quote(name) << ",\"nonce\":" << Quote(nonce)
            << ",\"cycles\":" << cycles << ",\"pending\":0,\"released_modules\":2,\"sdk_errors\":0,\"sdk_warnings\":"
            << diagnostics.warnings.load() << ",\"checks\":" << checks
            << ",\"debug_layer\":" << (debug_enabled ? "true" : "false") << ",\"debug_hresult\":" << static_cast<std::uint32_t>(debug_hr) << ",\"devices\":[";
        for (std::size_t i = 0; i < devices.size(); ++i) std::cout << (i ? "," : "") << devices[i];
        std::cout << "],\"readbacks\":[";
        for (std::size_t i = 0; i < records.size(); ++i) std::cout << (i ? "," : "") << records[i];
        std::cout << "],\"loaded\":" << loaded << "}\n" << std::flush;
        if (control == "deadline") std::this_thread::sleep_for(std::chrono::seconds(30));
        return 0;
    } catch (const std::exception& error) { std::cerr << "MW3_GPU_FAILURE:" << error.what() << '\n'; return 1; }
}
