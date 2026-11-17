# SPDX-License-Identifier: GPL-3.0-only
.text
.globl fixture
fixture:
    cmpw 3, 4
    li 3, -1
    blt .Ldone
    li 3, 1
.Ldone:
    blr
