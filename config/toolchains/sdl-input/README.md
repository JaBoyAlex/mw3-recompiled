# Opt-in SDL trigger-state profile

This is a modified SDL source profile for bounded MW3 host-input development.
It is not upstream SDL and does not replace an existing SDK. Preserve the
unaltered SDL notice in LICENSE.SDL and the original source's notices.

The lock binds SDL commit `147a8ee32dbf9ac02f3794964490687b6bbda1bc`, version
3.4.14, canonical Git source/declaration hashes and the one-file patch. Mapping
initialization still sets the trigger recentering point; a known axis sample
survives opening/remapping, while unknown initial state retains its default.

The producer builds an unpatched library, installs an independent baseline,
and then rebuilds its own source with the reviewed patch using the same
compiler/settings. One unchanged original probe executes both libraries.
Baselines retain their diagnostic failure; no value or stimulus is forced to
manufacture a repaired result. Existing SDKs and source checkouts are read-only.

Windows/Linux native builds and a Linux participating SDL ASan/UBSan profile
are separate identities. The ASan DSO resolves instrumentation from its
instrumented executable, so SDL's executable-oriented no-undefined linker
capability check is disabled for that profile only. Native profiles retain it.
This changes sanitizer linkage, not an SDL service result or guest import.

The source archive is exported with explicit LF checkout settings and checked
against every pinned Git blob before compilation. This avoids platform checkout
line-ending differences. Traversal, Windows rooted/device names, links,
duplicates and oversized archive members are rejected before extraction.

Private packages, baseline/repaired logs and full source/build trees are never
committed. See docs/engine/sdl-input-profile.md for exact evidence, commands and
coverage limits. Physical controllers, title input and game-linked distribution
remain independent work.
