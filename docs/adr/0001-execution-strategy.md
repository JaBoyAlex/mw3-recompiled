# ADR 0001: Console AOT with selective native replacement

Date: 2026-11-17. Status: accepted direction, runtime selection pending MW3-008.

The product needs original console gameplay/split-screen, native performance and maintainable small-team development. Full engine reconstruction would delay usable behavior; PC modification risks missing console local-player paths. Start with Xbox 360 ahead-of-time CPU translation and a proven runtime, then replace measured platform/render bottlenecks at documented seams. The owner supplied a USA/Korea Rev 1 image; its XEX identities are recorded separately from informal 1.1 labels.

Compare the related MW2 runtime and ReXGlue on an identical MW3 slice before selecting a permanent base. Correctness and licensing gate selection; performance carries the largest weighted score. Preserve original behavior as the oracle and add four-player Survival as a separately verified extension. Revisit this decision if measured integration, performance or rights constraints favor another path. No full decompilation percentage is a release requirement.
