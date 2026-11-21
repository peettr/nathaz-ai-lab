#!/usr/bin/env python3
"""Freeze T4 local stage without changing the baseline T3d root."""
from pathlib import Path
import shutil,hashlib,json,re,tarfile
R=Path(__file__).resolve().parent
T3=R.parent/'R21.4a_T3_emptyground/T3d/stage_fixed'
stage=R/'stage_t4'
assert not stage.exists() and not (R/'stage_t4.tar.gz').exists()
assert (R/'FluidX3D/src/defines.hpp').read_text().count('//#define GROUND_WALL_MODEL')==1
stage.mkdir()
shutil.copytree(R/'FluidX3D',stage/'FluidX3D_off')
shutil.copytree(R/'FluidX3D',stage/'FluidX3D_on')
p=stage/'FluidX3D_on/src/defines.hpp'; s=p.read_text().replace('//#define GROUND_WALL_MODEL // experimental flat-ground mirror and log-stress; default OFF, internal prototype only','#define GROUND_WALL_MODEL // T4 linked flat-ground specular reflection + log-stress; default OFF in source')
assert s!=p.read_text();p.write_text(s)
cases={}
for seed in (107,108,109):
 name=f'dx1p0_s{seed}'; dest=stage/name
 src=T3/name
 assert src.is_dir()
 shutil.copytree(src,dest)
 cases[name]={'conf_sha256':hashlib.sha256((dest/'conf.luwpf').read_bytes()).hexdigest(),
              'stl_sha256':hashlib.sha256((dest/'proj_temp/CaseE_PF.stl').read_bytes()).hexdigest(),
              'steps':71000,'avg_steps':60000,'stride':40}
smoke=stage/'smoke';shutil.copytree(stage/'dx1p0_s107',smoke)
p=smoke/'conf.luwpf';s=p.read_text();s=s.replace('cell_size = 1.0','cell_size = 5.0').replace('run_nstep = 71000','run_nstep = 11080').replace('purge_avg = 60000','purge_avg = 80').replace('purge_avg_stride = 40','purge_avg_stride = 2')
assert 'run_nstep = 11080' in s and 'cell_size = 5.0' in s;p.write_text(s)
manifest={'cases':cases,'smoke_conf_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
          'source_sha256':{name:hashlib.sha256((R/'FluidX3D/src'/name).read_bytes()).hexdigest() for name in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp')},
          'baseline_t3d':str(T3)}
(stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'stage_t4.tar.gz','w:gz') as t:t.add(stage,arcname='stage_t4')
print(json.dumps({'stage':str(stage),'bundle_sha256':hashlib.sha256((R/'stage_t4.tar.gz').read_bytes()).hexdigest(),'cases':cases,'smoke_conf_sha256':manifest['smoke_conf_sha256']},indent=2))
