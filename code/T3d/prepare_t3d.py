#!/usr/bin/env python3
"""Stage T3d from the immutable T3c package; no solver runs here."""
from pathlib import Path
import shutil,hashlib,json,tarfile,re
R=Path(__file__).resolve().parent; OLD=R.parent/'T3c'; S=R/'stage_fixed'
assert not S.exists() and not (R/'stage_t3d_bundle.tar.gz').exists()
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(OLD/'stage_fixed',S,symlinks=True)
man=json.loads((S/'stage_manifest.json').read_text())
assert H(S/'flatground.stl')==man['flatground_sha256']=='5deb3d977705b6f3a382eb22d4e17c0f0204e71e12ed10512c1528fe261450c6'
new={}
for seed in (107,108,109):
 for dx in ('1p0','0p5'):
  old=f'dx{dx}_s{105 if seed != 109 else 106}'; target=f'dx{dx}_s{seed}'
  if seed==109: # use the other template before renaming the 105 tree
   pass
  src=OLD/'stage_fixed'/old
  dest=S/target
  assert not dest.exists()
  shutil.copytree(src,dest,symlinks=True)
  conf=dest/'conf.luwpf';txt=conf.read_text();ref=int(old.split('_s')[1]);assert txt.count(f'vk_inlet_seed = {ref}')==1
  assert txt.count('run_nstep = '+('31000' if dx=='1p0' else '62000'))==1
  assert txt.count('purge_avg = '+('20000' if dx=='1p0' else '40000'))==1
  txt=txt.replace(f'vk_inlet_seed = {ref}',f'vk_inlet_seed = {seed}')
  steps=71000 if dx=='1p0' else 142000
  avg=60000 if dx=='1p0' else 120000
  txt=txt.replace('run_nstep = '+('31000' if dx=='1p0' else '62000'),f'run_nstep = {steps}')
  txt=txt.replace('purge_avg = '+('20000' if dx=='1p0' else '40000'),f'purge_avg = {avg}')
  conf.write_text(txt)
  c=man['cases'][old].copy();c.update(seed=seed,steps=steps,avg_steps=avg,conf_sha256=H(conf))
  assert c['stride']==(40 if dx=='1p0' else 80)
  for p in (dest/'proj_temp').glob('*.stl'):assert H(p)==man['flatground_sha256']
  new[target]=c
for p in S.glob('dx*_s10[56]'):shutil.rmtree(p)
man['cases']=new
setup=S/'FluidX3D/src/setup.cpp';txt=setup.read_text();assert txt.count('t3c_geometry_gate.csv')==1
txt=txt.replace('t3c_geometry_gate.csv','t3d_geometry_gate.csv').replace('T3c pre-solver geometry gate','T3d pre-solver geometry gate').replace('T3c gate','T3d gate').replace('T3c geometry gate','T3d geometry gate').replace('T3C_GEOMETRY','T3D_GEOMETRY')
setup.write_text(txt);man['setup_sha256']=H(setup)
(S/'stage_manifest.json').write_text(json.dumps(man,indent=2)+'\n')
with tarfile.open(R/'stage_t3d_bundle.tar.gz','w:gz') as tf:
 for item in sorted(S.rglob('*')):
  if item.is_file():tf.add(item,item.relative_to(S))
print(json.dumps({'stl_sha256':H(S/'flatground.stl'),'setup_sha256':H(setup),'cases':{k:v['conf_sha256'] for k,v in new.items()},'bundle_sha256':H(R/'stage_t3d_bundle.tar.gz')},indent=2))
