#!/usr/bin/env python3
"""Cross-step version-stamp audit on exact 24^3 build6 fixtures, no solver."""
import sys, json, pathlib
import numpy as np
BASE=pathlib.Path(__file__).resolve().parent
namespace={}
exec((BASE/'emu_facade_lead.py').read_text().split('out=[]')[0],namespace)
build=namespace['build'];make=namespace['make']

def audit(name, sf, steps=12):
    N,xyz,j,solid=build(24,24,24,sf)
    load,store,facade=make(N,j,solid)
    fluid=np.flatnonzero(~solid)
    fi=np.zeros((N,19),dtype=float)
    maps={}
    for on in (False,True):
        for parity in (0,1):
            slots=[]
            for n in fluid:
                reads={}; f=load(fi,int(n),parity,reads)
                if on: facade(fi,int(n),parity,f,reads)
                slots.append(int(n)*19) # stationary population: local read
                slots.extend(int(cell)*19+int(i) for cell,i in (reads[int(n),k] for k in range(1,19)))
            maps[on,parity]=np.array(slots,dtype=np.int32)
    writes={}
    for parity in (0,1):
        # Replicate store_f assignments, retaining last write to a slot.
        w=[]
        for n in fluid:
            w.append(int(n)*19)
            for i in range(1,19,2):
                w.extend((int(j[n,i])*19+(i+1 if parity else i),int(n)*19+(i if parity else i+1)))
        writes[parity]=np.array(w,dtype=np.int32)
    result=[]
    for on in (False,True):
        versions=np.full(N*19,-1,dtype=np.int32)
        read_counts={}; written=[]
        for t in range(steps):
            slots=maps[on,t%2]
            prior=versions[slots]
            for key,c in zip(zip(slots.tolist(),prior.tolist()),[1]*len(slots)):
                if key[1]>=2:read_counts[key]=read_counts.get(key,0)+c
            w=writes[t%2]
            versions[w]=t
            if 2<=t<=steps-4: written.extend((int(s),t) for s in np.unique(w))
        dup=sum(c-1 for (s,v),c in read_counts.items() if 2<=v<=steps-4 and c>1)
        lost=sum((s,v) not in read_counts for s,v in written)
        phase=[]
        for parity in (0,1):
            pdup=sum(c-1 for (s,v),c in read_counts.items() if 2<=v<=steps-4 and v%2==parity and c>1)
            plost=sum((s,v) not in read_counts for s,v in written if v%2==parity)
            phase.append({'phase':'odd' if parity else 'even','read_gt_one':int(pdup),'never_read':int(plost)})
        item={'fixture':name,'on':on,'fluid_cells':len(fluid),'written_versions':len(written),'read_gt_one':int(dup),'never_read':int(lost),'by_write_phase':phase}
        result.append(item)
        if dup or lost: raise AssertionError(item)
    return result

def main():
    L=24
    tests=[('cube',lambda x,y,z:x==0 or y==0 or z==0 or x==L-1 or y==L-1 or z==L-1 or (8<=x<16 and 8<=y<16 and 8<=z<16)),('channel_x',lambda x,y,z:x<=2 or x>=L-3),('channel_y',lambda x,y,z:y<=2 or y>=L-3)]
    result=[]
    for name,func in tests:result+=audit(name,func)
    out=BASE/'audit_versions_output.json';out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
