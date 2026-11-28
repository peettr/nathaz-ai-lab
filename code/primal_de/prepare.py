from pathlib import Path
import json,re,shutil
p=Path(__file__).resolve().parent
for a in 'DEF':
 d=p/'cases'/a
 shutil.copytree(p.parent/'case',d)
 meta=d/'mesh_manifest.json'; m=json.loads(meta.read_text())
 if a in 'EF':
  f=d/'system/blockMeshDict'; t=f.read_text()
  def grade(b):
   vert=int(b[1].split()[0]); i=vert%4;j=vert%16//4;k=vert//16
   x,y,z=map(int,b[2].split()); z=z if k==0 else 17
   return f'hex ({b[1]}) ({x} {y} {z}) simpleGrading ({[4,1,.25][i]} {[4,1,.25][j]} {4 if k==0 else 1})'
  t,n=re.subn(r'hex \(([^)]+)\) \(([^)]+)\) simpleGrading \([^)]+\)',grade,t); assert n==17; f.write_text(t)
  m['expected_cells']=sum(__import__('math').prod(map(int,v.split())) for v in re.findall(r'hex \([^)]+\) \(([^)]+)\)',t));m['subdivisions'][2][1]=17;meta.write_text(json.dumps(m,indent=2)+'\n')
 (d/'sample_cells.json').write_text(json.dumps(dict(mesh_cells=m['expected_cells'],cell_ids=[]))+'\n'); (d/'expected_steps').write_text('3000\n');(d/'expected_cells').write_text(str(m['expected_cells'])+'\n')
 f=d/'system/controlDict';f.write_text(f.read_text().replace('writeInterval 999999;','writeInterval 3000;'))
 print(a,m['expected_cells'])
s=(p.parent/'primal_ab/primal_driver.py').read_text().replace('assert n==227656','assert n==int((case/"expected_cells").read_text())').replace('and delta<.005','and delta<.005')
assert 'p\'][0::3]' in s
(p/'primal_driver.py').write_text(s)
