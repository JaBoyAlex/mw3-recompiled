# SPDX-License-Identifier: GPL-3.0-only
"""Independent mathematical expectations; no decoder or translator implementation."""
from fractions import Fraction
import random
import struct

MASK=(1<<64)-1
def signed(x):return x-(1<<64) if x>>63 else x
def bits64(x):return struct.unpack('>Q',struct.pack('>d',x))[0]
def value64(x):return Fraction.from_float(struct.unpack('>d',struct.pack('>Q',x))[0])
def value32(x):return Fraction.from_float(struct.unpack('>f',struct.pack('>I',x))[0])
def rounded32(x):
    """One round-to-nearest/even of a rational, using integer division only."""
    sign=0x80000000 if x<0 else 0;x=abs(x)
    if not x:return sign
    exponent=x.numerator.bit_length()-x.denominator.bit_length()
    if x < Fraction(2)**exponent:exponent-=1
    step=Fraction(2)**max(exponent-23,-149)
    q,r=divmod(x.numerator*step.denominator,x.denominator*step.numerator)
    denominator=x.denominator*step.numerator
    if r*2>denominator or (r*2==denominator and q%2):q+=1
    if exponent < -126:return sign|q
    if q==(1<<24):q>>=1;exponent+=1
    if exponent>127:return sign|0x7f800000
    return sign|((exponent+127)<<23)|(q&0x7fffff)
def cr(x,so):
    # PowerPC 64-bit implementation in 32-bit execution mode: CR0 and CA
    # reflect the low word, while add/sub retain the 64-bit GPR result.
    word=x&0xffffffff
    return (8 if word>>31 else 4 if word else 2)|so

def cases(seed=0x20110360, count=128):
    rng=random.Random(seed);result=[]
    def add(function,inputs,outputs):
        result.append(dict(id=f'{function}-{len(result):05d}',function='test_'+function,
                           **{'in':inputs,'out':outputs}))
    edges=[0,1,2,(1<<31)-1,1<<31,(1<<32)-1,1<<32,(1<<63)-1,1<<63,MASK]
    pairs=[(a,b) for a in edges for b in edges]+[(rng.getrandbits(64),rng.getrandbits(64)) for _ in range(count)]
    for a,b in pairs:
        for carry in (0,1):
            so=(a^b)&1
            total=a+b+carry
            add('adde',dict(r4=a,r5=b,ca=carry,so=so),dict(r3=total&MASK,ca=int((a&0xffffffff)+(b&0xffffffff)+carry>0xffffffff),cr0=cr(total&MASK,so),so=so))
        total=a+b
        add('addc',dict(r4=a,r5=b,so=1),dict(r3=total&MASK,ca=int((a&0xffffffff)+(b&0xffffffff)>0xffffffff),cr0=cr(total&MASK,1),so=1))
        delta=(b-a)&MASK
        add('subf',dict(r4=a,r5=b,ca=1),dict(r3=delta,ca=1,cr0=cr(delta,0)))
        low=a&0xffffffff;rot=((low<<7)|(low>>25))&0xffffffff
        add('rotate',dict(r4=a),dict(r3=rot&0x00ffff00))
        low=a&0xffffffff;half=b&0xffff;data=low.to_bytes(4,'big')+half.to_bytes(2,'big')
        add('memory',dict(r4=a,r5=b),dict(r3=low,r7=half,r8=data[1],r9=int.from_bytes(data[:4],'little'),
            **{'mem'+str(i):v for i,v in enumerate(data)},mem6=0xa5))
        add('branch',dict(r4=a),dict(r3=(-signed(a) if signed(a)<0 else a+7)&MASK))
        saved={f'r{n}':0x1122334400000000+n for n in [2,13,*range(14,32)]}
        add('call',dict(r4=a,r5=b,lr=0x820ff000,**saved),dict(r3=(2*a+b)&MASK,r1=0x28000,lr=0x820ff000,**saved))
    for i in range(1,33):add('loop',dict(r4=i,r5=MASK-i),dict(r3=(i*(MASK-i))&MASK))
    fp=[(1.0,2.0),(-3.5,2.0),(0.0,0.0),(2.0**53,1.0),(2.0**-1022,2.0**-1022)]
    fp += [(rng.randint(-1<<20,1<<20)/256,rng.randint(-1<<20,1<<20)/256) for _ in range(count)]
    for a,b in fp:
        aa,bb=bits64(a),bits64(b)
        add('fadd',dict(f2=aa,f3=bb),dict(f1=bits64(float(value64(aa)+value64(bb)))))
    add('fadd',dict(f2=1<<63,f3=1<<63),dict(f1=1<<63))
    add('fadd',dict(f2=0x7ff8000000001234,f3=bits64(1.0)),dict(f1=dict(value=0x7ff8000000000000,mask=0x7ff8000000000000)))
    # Fused cancellation distinguishes one final rounding from a rounded product.
    triples=[(1+2.0**-27,1-2.0**-27,-1.0),(1.5,2.0,-3.0)]
    triples += [(rng.randint(-10000,10000)/16,rng.randint(-10000,10000)/16,rng.randint(-10000,10000)/16) for _ in range(count)]
    for a,b,c in triples:
        aa,bb,cc=map(bits64,(a,b,c));answer=value64(aa)*value64(bb)+value64(cc)
        add('fmadd',dict(f2=aa,f3=bb,f4=cc),dict(f1=bits64(float(answer))))
    for _ in range(count):
        a=[rng.getrandbits(32) for _ in range(4)];b=[rng.getrandbits(32) for _ in range(4)]
        inputs={**{f'v2_{i}':v for i,v in enumerate(a)},**{f'v3_{i}':v for i,v in enumerate(b)}}
        add('vadd',inputs,{f'v1_{i}':(a[i]+b[i])&0xffffffff for i in range(4)})
        add('vxor',inputs,{f'v1_{i}':a[i]^b[i] for i in range(4)})
    triples32=[(0x3f800001,0x3f7ffffe,0xbf800000),(0x3fc00000,0x40000000,0xc0400000)]
    triples32 += [(rng.choice([0x3f000000,0x3f800001,0xc0200000,0x00800000]),rng.choice([0x3f800000,0x3f7ffffe,0x40800000]),rng.choice([0,0xbf800000,0x3e800000])) for _ in range(count)]
    for offset in range(0,len(triples32),4):
        lanes=[triples32[(offset+i)%len(triples32)] for i in range(4)]
        ins={f'v{reg}_{i}':lanes[i][slot] for reg,slot in ((2,0),(3,1),(4,2)) for i in range(4)}
        add('vmadd',ins,{f'v1_{i}':rounded32(value32(a)*value32(b)+value32(c)) for i,(a,b,c) in enumerate(lanes)})
    return result
