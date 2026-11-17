// SPDX-License-Identifier: GPL-3.0-only
// Original experiment harness. Import traps are generated privately from the
// verified title inventory. A stop at an import is not successful title boot.
#include MW3_GENERATED_INIT
#include <rex/app/title_app.h>
#include <cstdio>
#include <cstdlib>

bool VerifyProbeImportStops(rex::kernel::TitleRuntime&);

class EntryProbe final : public rex::app::TitleApp {
 public:
  EntryProbe() : TitleApp("mw3_private_entry_probe", kPPCImageConfig) {}
 protected:
  // This probe approves no GPU/audio/input work. Removing those requirements
  // bounds the experiment; it cannot establish a complete native game boot.
  rex::AppSysRequirements GetRequirements() const override { return {}; }

  rex::Result<void> OnTitleLaunch(rex::kernel::TitleRuntime& runtime) override {
    if (!VerifyProbeImportStops(runtime)) {
      std::fputs("MW3_PROBE_IMPORT_GUARD_FAILED\n", stderr);
      std::fflush(stderr);
      std::_Exit(87);
    }
    std::fputs("MW3_PROBE_IMAGE_LOADED; all guest imports remain diagnostic stops\n", stderr);
    std::fflush(stderr);
    return rex::Ok();
  }
};

// The driver must check the exit status AND a private diagnostic. The SDK app
// main's exit code alone does not prove that launch or guest execution occurred.
REX_TITLE_APP(EntryProbe)
