# Allocation-import safety derivative

This small patch modifies the selected ReXGlue kernel only in private derived
sources. The original file identifies Xenia research code, Copyright 2022 Ben
Vanik, with 2026 ReXGlue adaptations by Tom Clay. Preserve their BSD notices
and the complete upstream LICENSE in every private derived source tree/package.
The original project tooling is GPL-3.0-only. This patch and local preparation
are not permission to distribute proprietary SDKs, title-derived objects or
any game-linked binary. The profile changes pointer rejection policy and
signed-size conversion; it does not certify retail-console ABI behavior.
