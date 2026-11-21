#!/usr/bin/env python3
"""Build v10 from the GPU-tested v5 tree with ONLY v6 eligibility change."""
from pathlib import Path
import shutil, hashlib, difflib, json, datetime
P=Path(__file__).resolve().parent
V5=P/'build5_20261117_1156/FluidX3D_facade_v5'
V6=P/'build6_20261117_123412/FluidX3D_facade_v6'
R=P/('build11_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
V10=R/'FluidX3D_facade_v10'
assert not R.exists()
old=(V5/'src/kernel.cpp').read_text()
new=(V6/'src/kernel.cpp').read_text()
a='  const uint3 xyz=coordinates(n);\n  if(xyz.x<=1u||xyz.x+2u>=def_Nx||xyz.y<=1u||xyz.y+2u>=def_Ny||xyz.z<=1u||xyz.z+2u>=def_Nz) return false;\n'
assert old.count(a)==1 and old.replace(a,'') != old
assert new[new.index('bool facade_eligible('):new.index(')+"#endif"+R(',new.index('bool facade_eligible('))] == old.replace(a,'')[old.index('bool facade_eligible('):old.replace(a,'').index(')+"#endif"+R(',old.index('bool facade_eligible('))]
shutil.copytree(V5,V10)
(V10/'src/kernel.cpp').write_text(old.replace(a,''))
files=[x for x in V10.rglob('*') if x.is_file()]
for label,src in [('v5',V5),('v6',V6)]:
 with (R/('diff_vs_'+label+'.patch')).open('x') as f:
  for p in files:
   q=src/p.relative_to(V10)
   if p.read_bytes()!=q.read_bytes():
    f.writelines(difflib.unified_diff(q.read_text().splitlines(keepends=True),p.read_text().splitlines(keepends=True),fromfile=label+'/'+p.relative_to(V10).as_posix(),tofile='v10/'+p.relative_to(V10).as_posix()))
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(R/'source_sha256.json').write_text(json.dumps({'members':{p.relative_to(V10).as_posix():h(p) for p in files},'diff_vs_v5_sha256':h(R/'diff_vs_v5.patch'),'diff_vs_v6_sha256':h(R/'diff_vs_v6.patch')},indent=2)+'\n')
print(R)
