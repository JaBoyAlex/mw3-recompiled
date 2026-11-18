# SPDX-License-Identifier: GPL-3.0-only
# Original synthetic programs. Numeric register names work with LLVM's assembler.
.text
.globl test_addc
test_addc:
  addc. 3,4,5
  blr
.globl test_adde
test_adde:
  adde. 3,4,5
  blr
.globl test_subf
test_subf:
  subf. 3,4,5
  blr
.globl test_rotate
test_rotate:
  rlwinm 3,4,7,8,23
  blr
.globl test_memory
test_memory:
  stw 4,0(6)
  lwz 3,0(6)
  sth 5,4(6)
  lhz 7,4(6)
  lbz 8,1(6)
  lwbrx 9,0,6
  blr
.globl test_branch
test_branch:
  cmpdi 0,4,0
  blt 0,1f
  addi 3,4,7
  b 2f
1:
  neg 3,4
2:
  blr
.globl test_loop
test_loop:
  mtctr 4
  li 3,0
1:
  add 3,3,5
  bdnz 1b
  blr
.globl test_call
test_call:
  mflr 0
  std 0,16(1)
  stdu 1,-64(1)
  std 31,32(1)
  mr 31,4
  bl test_callee
  add 3,3,31
  ld 31,32(1)
  addi 1,1,64
  ld 0,16(1)
  mtlr 0
  blr
.globl test_callee
test_callee:
  add 3,4,5
  blr
.globl test_fadd
test_fadd:
  fadd 1,2,3
  blr
.globl test_fmadd
test_fmadd:
  fmadd 1,2,3,4
  blr
.globl test_vadd
test_vadd:
  vadduwm 1,2,3
  blr
.globl test_vxor
test_vxor:
  vxor 1,2,3
  blr
.globl test_vmadd
test_vmadd:
  vmaddfp 1,2,3,4
  blr
