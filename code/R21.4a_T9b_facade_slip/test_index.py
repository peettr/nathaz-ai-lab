#!/usr/bin/env python3.10
"""Pure index-ownership check for candidate specular mapping; not a solver test."""
import collections, importlib.util, pathlib
p=pathlib.Path(__file__).with_name('build_variant.py')
spec=importlib.util.spec_from_file_location('variant',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
V=m.V; N=12
solid={(x,y,z) for x in range(4,8) for y in range(4,8) for z in range(1,7)} | {(x,y,0) for x in range(N) for y in range(N)}
fluid={(x,y,z) for x in range(2,10) for y in range(2,10) for z in range(1,9)}-solid
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def opposite(i):return i+1 if i%2 else i-1
for parity in (0,1):
 counts=collections.Counter();native=collections.Counter();changed=collections.Counter();corner=0;affected=set()
 for n in fluid:
  cardinal={d:add(n,V[d]) in solid for d in (1,2,3,4)}
  one=sum(cardinal.values())==1
  for i,v in enumerate(V[1:],1):
   if i%2: address=(n,i if parity else i+1)
   else: address=(add(n,V[i-1]),i if parity else i-1)
   origin=address;native[origin]+=1
   if i>=7 and one:
    for axis,idxplus,idxminus in ((0,1,2),(1,3,4)):
     if not v[axis]:continue
     norm=tuple(-v[axis] if k==axis else 0 for k in range(3))
     t=tuple(v[k] if k!=axis else 0 for k in range(3))
     face=idxplus if norm[axis]==1 else idxminus
     src=sub(n,t)
     if (not cardinal[face] or sub(n,v) not in solid or src not in fluid or add(src,norm) not in solid):continue
     mirror=V.index(add(norm,t))
     address=(add(n,norm) if mirror%2 else src,mirror if parity else (mirror+1 if mirror%2 else mirror-1))
     changed[origin]+=1;affected.add(n)
   counts[address]+=1
 print('parity',parity,'candidate_sites',len(affected),'changed_links',sum(changed.values()),'unique_origins',len(changed),'delta_addresses',sum((native-counts).values())+sum((counts-native).values()))
 assert all(v==1 for v in changed.values())
 assert counts==native,[(k,native[k],counts[k]) for k in set(native)|set(counts) if native[k]!=counts[k]][:12]
assert m.generate().count('mirror_out=')==16
print('PASS: 16 directional formulas constructed; analytical index enumeration only, no physical cube gate')
