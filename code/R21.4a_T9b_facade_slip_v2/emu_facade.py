#!/usr/bin/env python3.10
"""Esoteric-Pull x/y facade link ledger; read-only CPU emulation, no CFD solve."""
from collections import Counter
import json
from pathlib import Path
C=((0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),(0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1))
N=12
SOLID={(x,y,z) for x in range(4,8) for y in range(4,8) for z in range(1,7)}|{(x,y,0) for x in range(N) for y in range(N)}
def add(a,b): return tuple((a[k]+b[k])%N for k in range(3))
def neg(a): return tuple(-v for v in a)
def sub(a,b): return add(a,neg(b))
def eligible(n,solid=SOLID):
    if n in solid or n[2] <= 1 or n[2]>=N-2 or n[0]<=1 or n[1]<=1 or n[0]>=N-2 or n[1]>=N-2:return None
    normals=[v for v in C[1:5] if add(n,v) in solid]
    if len(normals)!=1:return None
    normal=normals[0]
    # Exclude top/bottom, multi-axis corners and any unsupported diagonal.
    if add(n,C[5]) in solid or add(n,C[6]) in solid:return None
    return normal

def address(n,i,parity):
    if i==0:return n,0
    if i%2:return n,(i if parity else i+1)
    return add(n,C[i-1]),(i if parity else i-1)

def mirror_address(n,i,parity):
    normal=eligible(n)
    if normal is None or i<7:return None
    inward=neg(normal)
    if sum(C[i][k]*inward[k] for k in range(3))!=1:return None
    tangent=tuple(C[i][k]-inward[k] for k in range(3))
    if tangent==(0,0,0):return None
    partner=sub(n,tangent)
    if eligible(partner)!=normal or sub(n,C[i]) not in SOLID or add(partner,normal) not in SOLID:return None
    m=C.index(tuple(normal[k]+tangent[k] for k in range(3)))
    # Mirrored outgoing was written in the previous store_f, not current store_f.
    return (add(n,normal) if m%2 else partner, m if parity else (m+1 if m%2 else m-1))

def run():
    f=[(x,y,z) for x in range(N) for y in range(N) for z in range(N) if (x,y,z) not in SOLID]
    results=[]
    for parity in (0,1):
        old=Counter();new=Counter();modified=[]
        for n in f:
            for i in range(1,19):
                a=address(n,i,parity);b=mirror_address(n,i,parity) or a
                old[a]+=1;new[b]+=1
                if a!=b:modified.append((n,i,a,b))
        # A mirror intentionally changes the address set; old == new is NOT an invariant.
        # Check no packet is consumed twice, and each mirrored read is exactly a prior
        # store_f of its tangential source (including parity), as in the ground template.
        prior=1-parity
        bad=[]
        for n,i,_,b in modified:
            normal=eligible(n); inward=neg(normal)
            tangent=tuple(C[i][k]-inward[k] for k in range(3))
            partner=sub(n,tangent)
            m=C.index(tuple(normal[k]+tangent[k] for k in range(3)))
            store=(add(partner,C[m]),(m+1 if prior else m)) if m%2 else (partner,(m-1 if prior else m))
            if store!=b:bad.append((n,i,b,store))
        results.append(dict(parity=parity,eligible_cells=sum(eligible(n) is not None for n in f),changed_links=len(modified),unique_read_addresses=len(new),total_reads=sum(new.values()),duplicate_reads=sum(v-1 for v in new.values()),prior_store_mismatch=len(bad),sample_mismatch=bad[:4],changed_address_count=sum((old-new).values())))
    print(json.dumps(results,indent=2));return results
if __name__=='__main__':
    out=run();Path(__file__).with_name('emu_facade_output.json').write_text(json.dumps(out,indent=2)+'\n')
    assert all(x['duplicate_reads']==x['prior_store_mismatch']==0 for x in out), 'link address bijection failed; no GPU allocation permitted'
