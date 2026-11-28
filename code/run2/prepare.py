#!/usr/bin/env python3
"""Create immutable run2 decks from the archived T3 source (no solver execution)."""
from pathlib import Path
import shutil,struct,hashlib,json,tarfile,math
R=Path(__file__).resolve().parent; P=R.parent
assert not (R/'stage').exists(), 'run2 stage already exists'
assert (P/'stage_manifest.json').is_file()
old=json.loads((P/'stage_manifest.json').read_text())
assert old['domain_m']==[500,30,270] and old['xc_m']+50<350
stage=R/'stage';stage.mkdir()
shutil.copytree(P/'stage/FluidX3D',stage/'FluidX3D')
verts=[(0.,0.,-20.),(350.,0.,-20.),(350.,100.,-20.),(0.,100.,-20.),(0.,0.,0.),(350.,0.,0.),(350.,100.,0.),(0.,100.,0.)]
faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
with (stage/'flatground.stl').open('xb') as f:
 f.write(b'T3 run2 flat ground'.ljust(80,b' '));f.write(struct.pack('<I',len(faces)))
 for a,b,c in faces:f.write(struct.pack('<12fH',0.,0.,0.,*verts[a],*verts[b],*verts[c],0))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=(P/'stage/dx1p0_s101/conf.luwpf').read_text()
assert base.count('si_x_cfd = [0.000000, 500.000000]')==1 and base.count('si_y_cfd = [0.000000, 30.000000]')==1
m={'xc_m':old['xc_m'],'domain_m':[350,100,270],'sponge_m':200,'center_band_y_m':[40,60],'side_profile_y_m':[2,10,20,30,40,45,50,55,60,70,80,90,98],'setup_sha256':sha(stage/'FluidX3D/src/setup.cpp'),'defines_sha256':sha(stage/'FluidX3D/src/defines.hpp'),'flatground_sha256':sha(stage/'flatground.stl'),'cases':{}}
for dx in (1.,.5):
 for seed in (101,102):
  name=f'dx{str(dx).replace(".","p")}_s{seed}'; dest=stage/name
  (dest/'proj_temp').mkdir(parents=True);(dest/'wind_bc').mkdir()
  shutil.copyfile(stage/'flatground.stl',dest/'proj_temp/CaseE_PF.stl')
  shutil.copyfile(P/'stage/dx1p0_s101/wind_bc/profile.dat',dest/'wind_bc/profile.dat')
  text=base.replace('si_x_cfd = [0.000000, 500.000000]','si_x_cfd = [0.000000, 350.000000]').replace('si_y_cfd = [0.000000, 30.000000]','si_y_cfd = [0.000000, 100.000000]').replace('cell_size = 1.0',f'cell_size = {dx:.1f}').replace('run_nstep = 31000',f'run_nstep = {round(31000/dx)}').replace('purge_avg = 20000',f'purge_avg = {round(20000/dx)}').replace('purge_avg_stride = 40',f'purge_avg_stride = {round(40/dx)}').replace('vk_inlet_seed = 101',f'vk_inlet_seed = {seed}')
  assert text!=base and text.count(f'vk_inlet_seed = {seed}')==1
  conf=dest/'conf.luwpf';conf.write_text(text)
  m['cases'][name]={'dx':dx,'seed':seed,'cells_total':round(350/dx)*round(100/dx)*round(470/dx),'core_cells':round(350/dx)*round(100/dx)*round(270/dx),'steps':round(31000/dx),'avg_steps':round(20000/dx),'stride':round(40/dx),'conf_sha256':sha(conf)}
(stage/'stage_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
# Exact source archive for Colab upload; no large numerical output on 工作站.
with tarfile.open(R/'stage_bundle.tar.gz','w:gz') as tf:
 for p in sorted(stage.rglob('*')):
  if p.is_file():tf.add(p,arcname=p.relative_to(stage))
ref=1730
for name,c in m['cases'].items():
 seconds=ref*c['cells_total']/(500*500*470)*c['steps']/31000
 c['solver_reference_seconds']=seconds;c['conservative_CU']= (2*seconds/3600)*6.81+0.7
m['conservative_total_CU']=sum(c['conservative_CU'] for c in m['cases'].values())
assert m['conservative_total_CU']+2<60,m['conservative_total_CU']
(stage/'stage_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
# Update archive to contain same final manifest, not initial manifest.
(R/'stage_bundle.tar.gz').unlink()
with tarfile.open(R/'stage_bundle.tar.gz','w:gz') as tf:
 for p in sorted(stage.rglob('*')):
  if p.is_file():tf.add(p,arcname=p.relative_to(stage))
print(json.dumps({'archive_sha256':sha(R/'stage_bundle.tar.gz'),'manifest':m},indent=2))
