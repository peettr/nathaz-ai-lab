#!/usr/bin/env python3
"""Regenerate U/k/omega neutral-ABL fixedValue lists from ASCII mesh faces."""
from pathlib import Path
import sys,re,math
case=Path(sys.argv[1]); mesh=case/'constant/polyMesh'
boundary=(mesh/'boundary').read_text()
m=re.search(r'\binlet\s*\{([^}]+)\}',boundary); assert m
n=int(re.search(r'\bnFaces\s+(\d+)',m[1])[1]);start=int(re.search(r'\bstartFace\s+(\d+)',m[1])[1])
def listbody(name):
    s=(mesh/name).read_text();assert re.search(r'\bformat\s+ascii\s*;',s[:4096])
    # Read the first top-level list after the FoamFile header.
    s=s[s.index('FoamFile'):];s=s[s.index('}')+1:]
    m=re.search(r'\b(\d+)\s*\(',s);assert m,name
    size=int(m[1]); body=s[m.end():];return size,body
np,pb=listbody('points');nf,fb=listbody('faces')
points=re.findall(r'\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)',pb)
faces=re.findall(r'\b(\d+)\s*\(([^()]*)\)',fb)
assert len(points)==np,(len(points),np)
assert len(faces)==nf,(len(faces),nf)
assert start+n<=nf
kappa=.41;z0=.03;cmu=.09;ustar=kappa*10/math.log((8+z0)/z0)
vals={x:[] for x in ('U','nuTilda')};zs=[]
for face in faces[start:start+n]:
    ids=list(map(int,face[1].split()));assert len(ids)==int(face[0]) and len(ids)>=3
    z=sum(float(points[i][2]) for i in ids)/len(ids);assert math.isfinite(z) and z>=0
    zs.append(z)
    vals['U'].append(f'({ustar/kappa*math.log((z+z0)/z0):.12g} 0 0)')
    vals['nuTilda'].append(f'{kappa*ustar*(z+z0):.12g}')
for name,data in vals.items():
    path=case/'0'/name;s=path.read_text()
    replacement='inlet { type fixedValue; value nonuniform List<'+('vector' if name=='U' else 'scalar')+f'> {n}\n(\n'+'\n'.join(data)+'\n); }'
    s,count=re.subn(r'\binlet\s*\{[^{}]*\}',replacement,s,count=1,flags=re.S)
    assert count==1
    path.write_text(s)
print('SA_INLET',n,'HEIGHT',min(zs),max(zs),'USTAR',ustar,'MIN',min(map(float,vals['nuTilda'])),'MAX',max(map(float,vals['nuTilda'])))
