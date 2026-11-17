# SPDX-License-Identifier: GPL-3.0-only
.text
.globl fixture
fixture:
    stw 3, 0(5)
    lwz 4, 0(5)
    lhz 6, 0(5)
    lbz 7, 3(5)
    blr
