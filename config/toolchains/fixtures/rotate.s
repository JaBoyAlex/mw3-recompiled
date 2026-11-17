# SPDX-License-Identifier: GPL-3.0-only
.text
.globl fixture
fixture:
    rlwinm 3, 3, 8, 0, 31
    blr
