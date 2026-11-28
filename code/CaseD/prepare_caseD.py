#!/usr/bin/env python3
"""Build Case D deck without modifying original C38.2 inputs."""
from pathlib import Path
import csv, hashlib, json, re, struct
ROOT=Path(__file__).resolve().parents[3]
INPUT=ROOT.parent/'38_Collaborative_Research_Lab/06_Work/C38.2'
STAGE=ROOT/'06_Logs/caseA_r9_2m_tacc_v2/stage/caseA'
OUT=Path(__file__).resolve().parent/'stage'
assert not (OUT/'manifest.json').exists(), 'completed stage already exists'
(OUT/'caseD/proj_temp').mkdir(parents=True,exist_ok=True)
(OUT/'caseD/wind_bc').mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=INPUT/'data_AIJ_CaseD_zenodo15402669/BD_caseD.stl'
text=src.read_text()
vert=re.compile(r'(\bvertex\s+)([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)')
assert len(vert.findall(text))>100
# The original mesh facets and normals are unchanged under translation and positive uniform scale.
def rewrite(m):
 x,y,z=map(float,m.group(2,3,4));return f'{m.group(1)}{x*400+850:.9f} {y*400+550:.9f} {z*400:.9f}'
body=vert.sub(rewrite,text)
# Closed, outward oriented full-domain ground slab. The plate spans the source x width,
# preventing LUW's implicit STL-x-bound normalization from deforming the buildings.
lo=(0.,0.,-20.);hi=(1700.,1100.,0.)
P=[(lo[0],lo[1],lo[2]),(hi[0],lo[1],lo[2]),(hi[0],hi[1],lo[2]),(lo[0],hi[1],lo[2]),(lo[0],lo[1],hi[2]),(hi[0],lo[1],hi[2]),(hi[0],hi[1],hi[2]),(lo[0],hi[1],hi[2])]
faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
slab=['solid full_domain_ground']
for a,b,c,d in faces:
 for tri in ((a,b,c),(a,c,d)):
  slab+=[' facet normal 0 0 0','  outer loop']
  slab += ['   vertex %.9f %.9f %.9f'%P[i] for i in tri]
  slab+=['  endloop',' endfacet']
slab+=['endsolid full_domain_ground']
# Avoid multiple STL `solid` delimiters: the reader consumes a single ASCII solid.
body='\n'.join(line for line in body.splitlines() if not line.lstrip().startswith(('solid ','endsolid ')))
outstl=OUT/'caseD/proj_temp/CaseD_PF.stl'
stl_content='solid CaseD_PF\n'+body+'\n'+'\n'.join(slab[1:-1])+'\nendsolid CaseD_PF\n'
if outstl.exists(): assert outstl.read_text()==stl_content, 'existing stage differs'
else:
 with outstl.open('x') as f:f.write(stl_content)
assert outstl.stat().st_size>src.stat().st_size
profile=INPUT/'data_AIJ_CaseD_zenodo15402669/AF_caseD.csv'
with profile.open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
assert len(rows)>2
samples=[(float(r['z[m]'])*400,float(r['U[m/s]'])) for r in rows]
assert all(samples[i][0]<samples[i+1][0] for i in range(len(samples)-1))
# Above the last tunnel measurement (480 m full scale), hold the last measured U;
# no unsupported extrapolation of slope to the 600 m domain top.
pfile=OUT/'caseD/wind_bc/profile.dat'
pfile.write_text('z U\n'+''.join(f'{z:.9f} {u:.9f}\n' for z,u in samples))
conf=(STAGE/'conf.luwpf').read_text()
for old,new in [('casename = CaseA','casename = CaseD'),('1088.000000','1700.000000'),('704.000000','1100.000000'),('384.000000','600.000000'),('run_nstep = 32000','run_nstep = 33767'),('purge_avg = 22000','purge_avg = 23215'),('purge_avg_stride = 40','purge_avg_stride = 42')]:
 assert conf.count(old)==1,(old,conf.count(old));conf=conf.replace(old,new)
(OUT/'caseD/conf.luwpf').write_text(conf)
manifest={'input_sha256':{str(src):sha(src),str(profile):sha(profile)},'output_sha256':{str(p.relative_to(OUT)):sha(p) for p in (outstl,pfile,OUT/'caseD/conf.luwpf')},'n_source_triangles':len(vert.findall(text))//3,'source_bounds_model_m':[-.7,.7,-.675,.675,0,.25],'domain_m':[1700,1100,600],'stl_bounds_m':[0,1700,0,1100,-20,100],'profile_top_m':samples[-1][0],'profile_top_behavior':'hold last measured U above profile top','C38_to_LUW_xyz_m':'x+850,y+550,z; input STL model vertices times 400'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
