// SPDX-License-Identifier: GPL-3.0-only
// Original non-game shader: compile-only check; no GPU execution claimed.
float4 main(float4 position : SV_Position) : SV_Target0 {
    return float4(position.xy * 0.001, 0.5, 1.0);
}
