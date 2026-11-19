// SPDX-License-Identifier: GPL-3.0-only
// Original game-free lifecycle cases importing the actual SDK kernel library.
#include <rex/app/app.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/platform/thread.h>
#include <rex/ppc/image.h>
#include <rex/ppc/recompiled_code.h>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <string>

namespace {
namespace k = rex::kernel;
struct ContractApp : rex::app::App {
  ContractApp() : App("mw3_xma_lifecycle") {}
  rex::AppSysRequirements GetRequirements() const override { return {}; }
};
// No title bytes, generated code or guest instructions are embedded or executed.
const PPCFuncMapping mappings[] = {{0, nullptr}};
const rex::ppc::PPCImage image{0x82090000, 0x10000, 0x82000000, 0x100000, mappings};
void Require(bool condition, const char* reason) {
  if (!condition) throw std::runtime_error(reason);
}
int Run(ContractApp& app, const rex::CLIArgList& args) {
  const auto* value = std::getenv("MW3_XMA_CASE");
  const std::string mode = value ? value : "";
  Require(mode == "unloaded" || mode == "loaded" || mode == "launch-failure" || mode == "repeat", "unknown case");
  const auto before = rex::platform::detail::GetThreadCount();
  if (!app.Init(args)) return 2;
  try {
    const unsigned cycles = mode == "repeat" ? 4 : 1;
    for (unsigned cycle = 0; cycle < cycles; ++cycle) {
      auto runtime = std::make_unique<k::TitleRuntime>(image);
      if (mode != "unloaded") {
        Require(bool(runtime->GetTitlePaths().entry.Set("")), "empty synthetic entry rejected");
        Require(bool(runtime->Load()), "empty synthetic load failed");
        if (mode == "launch-failure" || mode == "repeat") {
          // Launch attaches the actual APU and its context pool before it
          // rejects the intentionally absent executable module. It must undo
          // those systems on this error path. No missing service is stubbed.
          auto launched = runtime->Launch();
          Require(!launched, "empty image unexpectedly launched");
          Require(launched.error().message == "the title's main thread could not be created",
                  "launch failed before the reviewed pool checkpoint");
          Require(!runtime->IsLoaded(), "failed launch did not unload");
          std::fprintf(stderr, "MW3_XMA_POOL_DESTROYED:cycle=%u\n", cycle);
        }
      }
      runtime->Unload();
      runtime->Unload();
      Require(!runtime->IsLoaded() && !runtime->IsRunning(), "runtime remained active");
      runtime.reset();
      Require(k::GetProcessRuntime() == nullptr, "process runtime remained installed");
    }
    Require(app.Shutdown() == 0, "app shutdown failed");
    const auto after = rex::platform::detail::GetThreadCount();
    Require(before == after, "SDK host thread count did not recover");
    std::fprintf(stderr, "MW3_XMA_COMPLETE:case=%s cycles=%u threads_before=%llu threads_after=%llu\n",
                 mode.c_str(), cycles, static_cast<unsigned long long>(before), static_cast<unsigned long long>(after));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "MW3_XMA_FAILURE:%s\n", error.what());
    app.Shutdown();
    return 2;
  }
}
}  // namespace
REX_CONSOLE_APP_MAIN(ContractApp, Run)
