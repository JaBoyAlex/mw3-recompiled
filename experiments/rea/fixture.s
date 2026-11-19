# SPDX-License-Identifier: GPL-3.0-only
# Original static-analysis fixture. Never executed; no title addresses or bytes.
.text
.globl mw3_probe
.type mw3_probe,@function
mw3_probe:
  mflr 0
  stwu 1,-16(1)
  stw 0,20(1)
  bl mw3_leaf
  lwz 0,20(1)
  addi 1,1,16
  mtlr 0
  blr
.size mw3_probe,.-mw3_probe

.globl mw3_leaf
.type mw3_leaf,@function
mw3_leaf:
  addi 3,4,4660
  cmpwi 3,0
  beq mw3_zero
  addi 3,3,7
mw3_zero:
  blr
.size mw3_leaf,.-mw3_leaf

.globl mw3_data_ref
.type mw3_data_ref,@function
mw3_data_ref:
  lis 5,mw3_marker@ha
  addi 5,5,mw3_marker@l
  lwz 3,0(5)
  blr
.size mw3_data_ref,.-mw3_data_ref

.globl mw3_vmx128
.type mw3_vmx128,@function
mw3_vmx128:
  # Xenon lvx128 v64,r11,r12; generic PPC decoding is deliberately challenged.
  .long 0x100b60cb
  blr
.size mw3_vmx128,.-mw3_vmx128

.data
.balign 4
.globl mw3_marker
.type mw3_marker,@object
mw3_marker:
  .long 0x1234abcd
.size mw3_marker,4
