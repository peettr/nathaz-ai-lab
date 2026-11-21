#!/usr/bin/env python3
"""Lossless-to-float32 ASCII facet conversion; source and prior attempts read-only."""
from pathlib import Path
import hashlib, json, re, struct, tarfile, tempfile
R=Path(__file__).resolve().parent
SRC=R.parent/'CaseD/stage'
DEST=R/'stage'
assert not DEST.exists() and not (R/'cased_stage.tar.gz').exists()
tri_re=re.compile(r'\bfacet\s+normal\s+([^\n]+)\s+outer loop\s+vertex\s+([^\n]+)\s+vertex\s+([^\n]+)\s+vertex\s+([^\n]+)\s+endloop\s+endfacet',re.I)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def f32(x):return struct.unpack('<f',struct.pack('<f',float(x)))[0]
def bounds(vertices):return [[min(v[k] for v in vertices),max(v[k] for v in vertices)] for k in range(3)]
text=(SRC/'caseD/proj_temp/CaseD_PF.stl').read_text();matches=list(tri_re.finditer(text))
assert len(matches)>100 and text.count('endfacet')==len(matches)
triangles=[]
for match in matches:
 normal=tuple(map(f32,match.group(1).split()));verts=[tuple(map(f32,match.group(k).split())) for k in (2,3,4)]
 assert len(normal)==3 and all(len(v)==3 for v in verts)
 triangles.append((normal,verts))
DEST.mkdir(); (DEST/'caseD/proj_temp').mkdir(parents=True)
for rel in ('caseD/conf.luwpf','caseD/wind_bc/profile.dat','caseD_points.csv'):
 p=DEST/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((SRC/rel).read_bytes())
output=DEST/'caseD/proj_temp/CaseD_PF.stl'
with output.open('xb') as f:
 f.write(b'CaseD_PF binary STL (float32)'[:80].ljust(80,b' '));f.write(struct.pack('<I',len(triangles)))
 for normal,verts in triangles:f.write(struct.pack('<12fH',*normal,*(c for v in verts for c in v),0))
with output.open('rb') as f:
 f.seek(80);count=struct.unpack('<I',f.read(4))[0]; raw=f.read()
assert count==len(triangles) and len(raw)==count*50
readback=[]
for i in range(count):
 vals=struct.unpack_from('<12fH',raw,i*50);readback.append((tuple(vals[:3]),[tuple(vals[j:j+3]) for j in (3,6,9)]))
assert readback==triangles
va=[v for _,vs in triangles for v in vs];vb=[v for _,vs in readback for v in vs]
assert set(va)==set(vb) and bounds(va)==bounds(vb)
manifest=json.loads((SRC/'manifest.json').read_text());manifest['output_sha256']['caseD/proj_temp/CaseD_PF.stl']=sha(output)
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'cased_stage.tar.gz','x:gz') as t:
 for p in sorted(DEST.rglob('*')):
  if p.is_file():t.add(p,p.relative_to(DEST))
summary={'ascii_path':str(SRC/'caseD/proj_temp/CaseD_PF.stl'),'ascii_sha256':sha(SRC/'caseD/proj_temp/CaseD_PF.stl'),'binary_path':str(output),'binary_sha256':sha(output),'triangle_count_ascii':len(triangles),'triangle_count_binary':count,'bbox_xyz_m_after_float32':bounds(va),'vertex_set_identical_after_float32':True,'normal_and_triangle_order_identical_after_float32':True,'binary_file_bytes':output.stat().st_size,'stage_tar_sha256':sha(R/'cased_stage.tar.gz')}
(R/'stl_consistency.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
