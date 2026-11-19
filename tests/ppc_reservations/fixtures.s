# SPDX-License-Identifier: GPL-3.0-only
# Original aligned test instructions, not extracted from a title.
.text
.p2align 2
.globl test_load_w_zero
test_load_w_zero:
    lwarx 3,0,6
    blr
.globl test_store_w_zero
test_store_w_zero:
    stwcx. 5,0,6
    blr
.globl test_load_d_zero
test_load_d_zero:
    ldarx 3,0,6
    blr
.globl test_store_d_zero
test_store_d_zero:
    stdcx. 5,0,6
    blr
.globl test_load_w_index
test_load_w_index:
    lwarx 3,4,6
    blr
.globl test_store_w_index
test_store_w_index:
    stwcx. 5,4,6
    blr
.globl test_load_d_index
test_load_d_index:
    ldarx 3,4,6
    blr
.globl test_store_d_index
test_store_d_index:
    stdcx. 5,4,6
    blr
