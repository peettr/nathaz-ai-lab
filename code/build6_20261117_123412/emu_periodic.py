#!/usr/bin/env python3
"""Symbolic read/store address test using build6 periodic eligibility."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import emu_facade as e
N=e.N

def fixture(axis):
 return { (x,y,z) for x in range(N) for y in range(N) for z in range(N)
          if (x if axis=='x' else y)<=2 or (x if axis=='x' else y)>=N-3 }

def eligible(n,solid):
 if n in solid:return None
 normals=[v for v in e.C[1:5] if e.add(n,v) in solid]
 if len(normals)!=1:return None
 if e.add(n,e.C[5]) in solid or e.add(n,e.C[6]) in solid:return None
 return normals[0]

def test(axis):
 solid=fixture(axis)
 e.SOLID=solid
 # Existing mirror_address invokes module global eligible, so bind the new rule.
 e.eligible=lambda n:eligible(n,solid)
 fluid=((x,y,z) for x in range(N) for y in range(N) for z in range(N) if (x,y,z) not in solid)
 fluid=list(fluid);results=[]
 for parity in (0,1):
  reads=Counter();modified=[]
  for n in fluid:
   for i in range(1,19):
    a=e.address(n,i,parity);b=e.mirror_address(n,i,parity) or a
    reads[b]+=1
    if a!=b:modified.append((n,i,b))
  bad=[];prior=1-parity
  for n,i,b in modified:
   normal=e.eligible(n);inward=e.neg(normal)
   tangent=tuple(e.C[i][k]-inward[k] for k in range(3))
   partner=e.sub(n,tangent)
   m=e.C.index(tuple(normal[k]+tangent[k] for k in range(3)))
   store=(e.add(partner,e.C[m]),(m+1 if prior else m)) if m%2 else (partner,(m-1 if prior else m))
   if store!=b:bad.append((n,i,b,store))
  result=dict(fixture=axis,parity=parity,eligible_cells=sum(e.eligible(n) is not None for n in fluid),changed_links=len(modified),total_reads=sum(reads.values()),duplicate_reads=sum(v-1 for v in reads.values()),prior_store_mismatch=len(bad),sample_bad=bad[:2])
  results.append(result)
  assert result['changed_links']>0 and result['duplicate_reads']==result['prior_store_mismatch']==0,result
 return results
if __name__=='__main__':
 out=test('x')+test('y')
 path=Path(__file__).with_name('emu_periodic_output.json');path.write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out,indent=2))
