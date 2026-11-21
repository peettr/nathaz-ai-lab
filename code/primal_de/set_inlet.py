"""Assign fixedValue arrays in actual OpenFOAM ASCII patch-face order."""
from pathlib import Path
import math,re,sys,json

def body(path):
 s=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S)
 m=re.search(r'\bformat\s+ascii\s*;',s); assert m,path
 m=re.search(r'\}\s*(\d+)\s*\(',s); assert m,path
 return int(m[1]),s[m.end():]

def apply(case):
 mesh=case/'constant/polyMesh'; n,s=body(mesh/'points')
 pts=[tuple(map(float,t.split())) for t in re.findall(r'\(([^()]*)\)',s)]; assert len(pts)==n and all(len(t)==3 for t in pts)
 n,s=body(mesh/'faces'); fs=[tuple(map(int,t.split())) for t in re.findall(r'\d+\s*\(([^()]*)\)',s)]; assert len(fs)==n
 n,s=body(mesh/'boundary'); b=dict(re.findall(r'(\w+)\s*\{([^{}]+)\}',s)); assert len(b)==n
 k=int(re.search(r'startFace\s+(\d+);',b['inlet'])[1]); q=int(re.search(r'nFaces\s+(\d+);',b['inlet'])[1]); assert 0<q and k+q<=len(fs)
 zs=[]
 for f in fs[k:k+q]:
  xyz=[pts[i] for i in f]; assert len(xyz)==4 and all(abs(x)<1e-10 for x,y,z in xyz)
  assert len({(y,z) for x,y,z in xyz})==4 and len({y for x,y,z in xyz})==2 and len({z for x,y,z in xyz})==2
  zs.append(sum(z for x,y,z in xyz)/4)
 assert min(zs)>0 and max(zs)<4
 z0=.00375; kappa=.41; ustar=kappa/math.log1p(1/z0)
 values=[math.log1p(z/z0)*ustar/kappa for z in zs]; nut=[kappa*ustar*(z+z0) for z in zs]
 for field,kind,rows in [('U','vector',[f'({u:.15g} 0 0)' for u in values]),('nuTilda','scalar',[f'{v:.15g}' for v in nut])]:
  p=case/'0'/field; s=p.read_text(); s,count=re.subn(r'(\binlet\s*\{\s*type fixedValue;\s*)value uniform [^;]+;',lambda m:m[1]+f'value nonuniform List<{kind}>\n{q}\n(\n'+'\n'.join(rows)+'\n);',s); assert count==1;p.write_text(s)
 print(json.dumps(dict(inlet_faces=q,z_min=min(zs),z_max=max(zs),u_min=min(values),u_max=max(values),nuTilda_min=min(nut),nuTilda_max=max(nut),z0=z0,kappa=kappa,ustar=ustar)))
if __name__=='__main__': apply(Path(sys.argv[1]))
