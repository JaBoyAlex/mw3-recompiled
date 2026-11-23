// SPDX-License-Identifier: GPL-3.0-only
// Original synthetic callback addresses/data, never MW3 instructions or bindings.
#include <rex/app/app.h>
#include <rex/kernel/export.h>
#include <rex/kernel/guest_memory.h>
#include <rex/kernel/heap.h>
#include <rex/kernel/object/object_table.h>
#include <rex/kernel/thread_registry.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/kernel/types/thread.h>
#include <rex/logging/logger.h>
#include <rex/ppc/image.h>
#include "kernel/test_access.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace k = rex::kernel;
namespace {
using Clock = std::chrono::steady_clock;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
constexpr u32 scratch_size = 0x20000, code = 0x82100000, entry = code + 0x1000;
constexpr u64 poison = 0xa51b987600000000ull;
struct Failure : std::runtime_error { using std::runtime_error::runtime_error; };
void Check(bool value, const char* why) { if (!value) throw Failure(why); }
template<class T> void Ok(const T& value, const char* why) { Check(bool(value), why); }
u64 Elapsed(Clock::time_point start) { return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count(); }
std::string Quote(std::string_view text) {
    std::string result = "\""; constexpr char digits[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') { result += '\\'; result += static_cast<char>(c); }
        else if (c < 32) { result += "\\u00"; result += digits[c >> 4]; result += digits[c & 15]; }
        else result += static_cast<char>(c);
    }
    return result + '"';
}
std::string LoadedPath(const void* address) {
#ifdef _WIN32
    HMODULE module{}; std::array<wchar_t,32768> path{};
    Check(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
          reinterpret_cast<LPCWSTR>(address), &module) != 0, "loaded module lookup failed");
    const auto length = GetModuleFileNameW(module,path.data(),static_cast<DWORD>(path.size()));
    Check(length && length < path.size(), "loaded module path truncated");
    return std::filesystem::path(path.data()).generic_string();
#else
    Dl_info info{};
    Check(dladdr(address,&info) != 0 && info.dli_fname, "loaded module lookup failed");
    return std::filesystem::absolute(info.dli_fname).string();
#endif
}
struct Binding { const char* name; unsigned ordinal; const k::ExportEntry* actual{}; };
std::array<Binding,4> bindings{{{"VdQueryVideoMode",0x1ca}, {"VdGetCurrentDisplayInformation",0x1ba},
                            {"VdGetCurrentDisplayGamma",0x1b9}, {"VdQueryVideoFlags",0x1c9}}};
struct Input { unsigned service; u32 offset; };
std::vector<Input> ReadPlan(const char* path) {
    std::ifstream input(path); Check(bool(input), "original plan missing"); std::vector<Input> rows;
    for (std::string line; std::getline(input,line);) {
        std::istringstream row(line); Input value{}; std::string extra;
        Check(bool(row >> value.service >> value.offset) && !(row >> extra) && value.service < 4 &&
              value.offset >= 16 && value.offset % 16 == 0 && value.offset <= scratch_size-128,
              "invalid bounded original plan row");
        Check(rows.size() < 128, "too many original plan rows"); rows.push_back(value);
    }
    Check(input.eof() && rows.size() == 128, "incomplete original plan"); return rows;
}
std::array<u64,21> Preserved(PPCContext& c) {
    return {c.r1.u64,c.r2.u64,c.r13.u64,c.r14.u64,c.r15.u64,c.r16.u64,c.r17.u64,c.r18.u64,c.r19.u64,
            c.r20.u64,c.r21.u64,c.r22.u64,c.r23.u64,c.r24.u64,c.r25.u64,c.r26.u64,c.r27.u64,c.r28.u64,
            c.r29.u64,c.r30.u64,c.r31.u64};
}
std::string Numbers(const std::array<u64,21>& values) {
    std::string result = "[";
    for (std::size_t i=0;i<values.size();++i) result += (i ? "," : "") + std::to_string(values[i]);
    return result + ']';
}
struct Diagnostics final : rex::log::ILogSink {
    std::atomic_uint64_t errors{},warnings{};
    void Write(const rex::log::Message& message) override {
        if (message.level >= rex::log::Level::kError) ++errors;
        else if (message.level == rex::log::Level::kWarn) ++warnings;
    }
    void Flush() override {}
};
struct State {
    k::TitleRuntime* runtime{}; u32 scratch{}; std::vector<Input> plan;
    std::string scenario,nonce,failure;
    std::vector<std::string> rows;
    std::atomic<bool> completed{false};
};
std::atomic<State*> active{};

std::string Observe(State& state, PPCContext& context, u8* base, Input input, bool wrong, unsigned shift=16) {
    auto& memory = state.runtime->GetGuestMemory();
    auto writable = memory.GetWritableSpan(state.scratch,scratch_size); Ok(writable,"owned scratch not writable");
    std::fill(writable->begin(),writable->end(),std::byte{0xa7});
    const auto before = Preserved(context);
    context.r3.u64 = poison | (state.scratch+input.offset+shift);
    context.r4.u64 = poison | (state.scratch+input.offset+80);
    const auto start = Clock::now(); bindings[input.service].actual->fn(context,base); const auto elapsed = Elapsed(start);
    const auto after = Preserved(context);
    auto view = memory.GetReadOnlySpan(state.scratch,scratch_size); Ok(view,"scratch no longer readable");
    std::string hex; constexpr char digits[] = "0123456789abcdef";
    for (unsigned i=0;i<128;++i) {
        unsigned byte = std::to_integer<unsigned char>((*view)[input.offset+i]);
        if (wrong && i == 16) byte ^= 1;
        hex += digits[byte>>4]; hex += digits[byte&15];
    }
    bool external = true;
    for (u32 i=0;i<scratch_size;++i) if (i<input.offset || i>=input.offset+128) external &= (*view)[i] == std::byte{0xa7};
    return "{\"service\":"+std::to_string(input.service)+",\"offset\":"+std::to_string(input.offset)+
        ",\"bytes\":"+Quote(hex)+",\"r3\":"+std::to_string(context.r3.u64)+",\"before\":"+Numbers(before)+
        ",\"after\":"+Numbers(after)+",\"external_canary\":"+(external ? "true" : "false")+
        ",\"elapsed_ns\":"+std::to_string(elapsed)+'}';
}
void Boundary(State& state,PPCContext& context,u8* base) {
    auto& memory = state.runtime->GetGuestMemory();
    unsigned service=0; u32 address=0;
    if (state.scenario == "readonly-gamma") {
        service=2; address=state.scratch+16;
        Ok(memory.Protect(state.scratch,0x10000,k::GuestProtect::kReadOnly),"owned read-only fixture setup failed");
    } else if (state.scenario == "guard-display") {
        service=1; address=state.scratch+0xffe0;
        auto* heap=k::GetAddressSpace(*state.runtime).LookupHeap(state.scratch+0x10000);
        Check(heap && heap->Decommit(state.scratch+0x10000,0x10000),"owned guard fixture setup failed");
    } else if (state.scenario == "wrap-mode") address=0xfffffff0u;
    else Check(state.scenario == "null-mode","unknown boundary case");
    context.r3.u64=poison|address; context.r4.u64=poison|(state.scratch+80);
    const auto armed="{\"nonce\":"+Quote(state.nonce)+",\"case\":"+Quote(state.scenario)+
        ",\"service\":"+std::to_string(service)+",\"pointer\":"+std::to_string(address)+'}';
    std::printf("MW3_DISPLAY_ARMED:%s\n",armed.c_str()); std::fflush(stdout);
    bindings[service].actual->fn(context,base);
    const auto returned="{\"nonce\":"+Quote(state.nonce)+",\"case\":"+Quote(state.scenario)+
        ",\"r3\":"+std::to_string(context.r3.u64)+'}';
    std::printf("MW3_DISPLAY_BOUNDARY_RETURN:%s\n",returned.c_str());std::fflush(stdout);
}
void Entry(PPCContext& context,u8* base) {
    auto* state=active.load(std::memory_order_acquire);
    if (!state) { std::fputs("MW3_DISPLAY_FAILURE:missing owned callback state\n",stderr); std::_Exit(3); }
    try {
        auto* thread=k::KernelThread::GetCallingThread();
        Check(thread && &thread->GetRuntime()==state->runtime && context.r13.u32==thread->GetPCRPtr(),"not an initialized owned guest thread");
        PPCRegister* registers[]={&context.r14,&context.r15,&context.r16,&context.r17,&context.r18,&context.r19,&context.r20,&context.r21,
            &context.r22,&context.r23,&context.r24,&context.r25,&context.r26,&context.r27,&context.r28,&context.r29,&context.r30,&context.r31};
        for (unsigned i=0;i<18;++i) registers[i]->u64=0x5a51000000000000ull+i;
        if (state->scenario == "null-mode" || state->scenario == "readonly-gamma" || state->scenario == "guard-display" || state->scenario == "wrap-mode") {
            Boundary(*state,context,base);
        } else if (state->scenario == "misaligned-display") {
            const auto armed="{\"nonce\":"+Quote(state->nonce)+",\"case\":\"misaligned-display\",\"service\":1,\"pointer\":"+
                std::to_string(state->scratch+33)+'}';
            std::printf("MW3_DISPLAY_ARMED:%s\n",armed.c_str());std::fflush(stdout);
            state->rows.push_back(Observe(*state,context,base,{1,16},false,17));
        } else for (std::size_t i=0;i<state->plan.size();++i) {
            state->rows.push_back(Observe(*state,context,base,state->plan[i],state->scenario == "wrong-result" && i == 0));
        }
        context.r3.u64=0; state->completed.store(true,std::memory_order_release);
    } catch (const Failure& error) { state->failure=error.what();state->completed.store(true,std::memory_order_release);context.r3.u64=1; }
    // SDK ThreadStop must unwind to its real thread entry, never be swallowed.
}
const PPCFuncMapping mappings[]={{entry,&Entry},{0,nullptr}};
const rex::ppc::PPCImage image{code,0x10000,0x82000000,0x200000,mappings};
struct App final : rex::app::App { App():rex::app::App("mw3_original_display_queries"){} };
} // namespace

int main(int argc,char** argv) {
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
#endif
    if (argc != 4) { std::fputs("MW3_DISPLAY_FAILURE:arguments required\n",stderr);return 2; }
    const std::string scenario=argv[1],nonce=argv[2];
    const std::array<std::string_view,9> allowed{"ordinary","wrong-result","incomplete","deadline","null-mode","guard-display","readonly-gamma","wrap-mode","misaligned-display"};
    if (std::find(allowed.begin(),allowed.end(),scenario)==allowed.end() || nonce.size()!=32 ||
        !std::all_of(nonce.begin(),nonce.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');})) {
        std::fputs("MW3_DISPLAY_FAILURE:invalid case or nonce\n",stderr);return 2;
    }
    try {
        const auto plan=ReadPlan(argv[3]);std::string exports="[",kernel;
        for (std::size_t i=0;i<bindings.size();++i) {
            auto& binding=bindings[i];binding.actual=k::FindByOrdinal(k::ExportModule::kXboxkrnl,static_cast<u16>(binding.ordinal));
            Check(binding.actual && binding.actual->type==k::ExportType::kFunction && binding.actual->name==binding.name && binding.actual->fn,
                  "pinned actual export binding differs");
            const auto path=LoadedPath(reinterpret_cast<const void*>(binding.actual->fn));
            if (kernel.empty()) kernel=path;Check(path==kernel,"query exports belong to different modules");
            exports+=(i ? "," : "")+std::string("{\"name\":")+Quote(binding.name)+",\"ordinal\":"+std::to_string(binding.ordinal)+'}';
        }
        exports+=']';const std::string loaded="{\"kernel\":"+Quote(kernel)+",\"base\":"+
            Quote(LoadedPath(reinterpret_cast<const void*>(&rex::GetLogger)))+'}';
        std::printf("MW3_DISPLAY_LIBRARIES:{\"nonce\":%s,\"loaded\":%s,\"exports\":%s}\n",Quote(nonce).c_str(),loaded.c_str(),exports.c_str());std::fflush(stdout);
        const auto start=Clock::now();App app;
        const auto root=std::filesystem::current_path()/"profile";std::filesystem::create_directories(root);
        const std::vector<std::string> flags{"--app.root="+(root/"app").string(),"--app.user_root="+(root/"user").string(),
            "--app.cache_root="+(root/"cache").string(),"--title.game_root="+root.string(),"--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"};
        Ok(app.Init(rex::CLIArgList::Parse(flags)),"original app initialization failed");
        Diagnostics diagnostics;const auto sink=rex::GetLogger().AddSink(diagnostics);
        auto runtime=std::make_unique<k::TitleRuntime>(image);Ok(runtime->GetTitlePaths().entry.Set(""),"original empty entry rejected");
        Ok(runtime->Load(),"original runtime load failed");
        const auto pages_before=k::GetAddressSpace(*runtime).GetTitlePages();const auto objects_before=runtime->GetObjectTable().GetAll().size();
        auto allocation=runtime->GetGuestMemory().Allocate(scratch_size,0x10000,k::GuestProtect::kReadWrite,k::GuestHeap::kTitle);
        Ok(allocation,"original scratch allocation failed");
        auto writable=runtime->GetGuestMemory().GetWritableSpan(*allocation,scratch_size);Ok(writable,"original scratch unavailable");
        std::fill(writable->begin(),writable->end(),std::byte{0xa7});
        State state;state.runtime=runtime.get();state.scratch=*allocation;state.plan=plan;state.scenario=scenario;state.nonce=nonce;
        State* empty=nullptr;Check(active.compare_exchange_strong(empty,&state),"overlapping owned callback state");
        const rex::ScopeGuard unbind([&]{active.store(nullptr,std::memory_order_release);});
        auto worker=std::make_unique<k::KernelThread>(*runtime,0x10000,0,entry,0x51515151,0,true,false);
        auto launched=runtime->GetThreadRegistry().Launch(std::move(worker));Ok(launched,"owned original guest thread launch failed");
        const auto load_ns=Elapsed(start);u64 timeout=u64(-std::int64_t{100000000});
        Check(runtime->GetThreadRegistry().GetObjectWaiter().WaitGuestObject(*launched,0,0,0,&timeout)==0,"owned callback deadline");
        Check(state.completed.load(std::memory_order_acquire),"owned callback did not complete");
        auto pin=runtime->GetThreadRegistry().FindByHandle(*launched);Ok(pin,"completed original guest handle missing");
        auto object=runtime->GetGuestMemory().Load<k::X_KTHREAD>(pin->GetGuestObject());Ok(object,"completed original guest object missing");
        Check(object->terminated==1 && object->exit_status==(state.failure.empty()?0u:1u),"owned guest exit metadata differs");
        pin.Reset();k::CloseOwned(runtime->GetObjectTable(),*launched);
        Ok(runtime->GetGuestMemory().Free(*allocation),"owned scratch free failed");
        const auto pages_after=k::GetAddressSpace(*runtime).GetTitlePages();const auto objects_after=runtime->GetObjectTable().GetAll().size();
        const auto teardown=Clock::now();runtime->Unload();Check(!runtime->IsLoaded(),"original runtime remained loaded");
        runtime.reset();app.Shutdown();const auto teardown_ns=Elapsed(teardown);
        Check(state.failure.empty(),state.failure.c_str());Check(diagnostics.errors.load()==0,"SDK logged an error including teardown");
        std::printf("MW3_DISPLAY_READY:%s\n",nonce.c_str());std::fflush(stdout);
        if (scenario=="incomplete") return 0;
        std::ostringstream result;
        result << "{\"schema\":1,\"case\":" << Quote(scenario) << ",\"nonce\":" << Quote(nonce)
            << ",\"pages_before\":" << pages_before << ",\"pages_after\":" << pages_after
            << ",\"objects_before\":" << objects_before << ",\"objects_after\":" << objects_after
            << ",\"runtime_loaded_after\":false,\"sdk_errors\":" << diagnostics.errors.load() << ",\"sdk_warnings\":" << diagnostics.warnings.load()
            << ",\"load_ns\":" << load_ns << ",\"teardown_ns\":" << teardown_ns << ",\"rows\":[";
        for (std::size_t i=0;i<state.rows.size();++i) result << (i?",":"") << state.rows[i];
        result << "],\"loaded\":" << loaded << ",\"exports\":" << exports << '}';
        std::printf("MW3_DISPLAY_COMPLETE:%s\n",result.str().c_str());std::fflush(stdout);
        if (scenario=="deadline") std::this_thread::sleep_for(std::chrono::seconds(30));
        return 0;
    } catch(const std::exception& error) {std::fprintf(stderr,"MW3_DISPLAY_FAILURE:%s\n",error.what());return 1;}
}
