#!/usr/bin/env python3.10
"""Create an immutable, fresh four-case input archive; never run a solver locally."""
import pathlib,tarfile,shutil,hashlib,json,re
R=pathlib.Path(__file__).resolve().parent; LOGS=R.parent
T4=LOGS/'R21.4a_T4_groundWM/phaseB_v2/stage/FluidX3D_on'
B2=LOGS/'tacc_feasibility/T2d_a/B2u_inputs.tar.gz'
S=R/'stage';assert not S.exists() and T4.is_dir() and B2.is_file()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
S.mkdir(); manifest={'base_archive_sha256':sha(B2),'source':{},'cases':{}}
shutil.copytree(T4,S/'FluidX3D_on',symlinks=True)
shutil.copytree(T4,S/'FluidX3D_off',symlinks=True)
on=(S/'FluidX3D_on/src/defines.hpp').read_text();line='#define GROUND_WALL_MODEL // T4 linked flat-ground specular reflection + log-stress; default OFF in source'
assert on.count(line)==1
(S/'FluidX3D_off/src/defines.hpp').write_text(on.replace(line,'//#define GROUND_WALL_MODEL // T5 OFF'))
# The inherited T3d fixture gate addresses y=50 m and fails inside Case E buildings.
# Remove only this fixture-specific diagnostic (not the geometry, boundary or wall model).
for variant in ('on','off'):
 p=S/f'FluidX3D_{variant}/src/setup.cpp';s=p.read_text()
 first=s.index('            {\n                const float x_sites[] = {0.0f, 1.0f, 5.0f, 252.0f, 500.0f};')
 last=s.index('\n            }',first)+len('\n            }')
 assert 'T3d geometry gate failed before solver' in s[first:last]
 s=s[:first]+'            // T5 Case E: T3d open-ground fixture gate removed; city geometry preserved.'+s[last:]
 assert s.count('cfg.ground_z_lbm = units.x(z_si_offset);')==1
 p.write_text(s)
 manifest['source'][variant]={n:sha(S/f'FluidX3D_{variant}/src'/n) for n in ('setup.cpp','defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp')}
with tarfile.open(B2) as t:
 names=t.getnames();assert all(n=='FluidX3D' or n.startswith('FluidX3D/') or n=='case' or n.startswith('case/') for n in names)
 for member in t:
  if member.name in ('case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl'):
   data=t.extractfile(member).read();p=S/member.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
conf=(S/'case/conf.luwpf').read_text();assert 'si_x_cfd = [0.000000, 500.000000]' in conf and 'si_y_cfd = [0.000000, 500.000000]' in conf and 'si_z_cfd = [0.000000, 270.000000]' in conf
assert all(x in conf for x in ('n_gpu = [1, 1, 1]','run_nstep = 31000','purge_avg = 20000','purge_avg_stride = 40','cell_size = 1.0'))
assert 'vk_inlet_seed' not in conf
for seed in (101,102):
 for variant in ('off','on'):
  label=f'E_s{seed}_{variant}';d=S/'cases'/label
  (d/'proj_temp').mkdir(parents=True);(d/'wind_bc').mkdir()
  for rel in ('wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):shutil.copyfile(S/'case'/rel,d/rel)
  (d/'conf.luwpf').write_text(conf+f'\n// T5 seed; only model switch is in compiled defines.hpp\nvk_inlet_seed = {seed}\n')
  manifest['cases'][label]={'config_sha256':sha(d/'conf.luwpf'),'seed':seed,'variant':variant,'steps':31000,'avg_steps':20000,'avg_samples':500,'core_grid':[500,500,270],'full_grid_expected':[500,500,470]}
manifest['stl_sha256']=sha(S/'case/proj_temp/CaseE_PF.stl');manifest['profile_sha256']=sha(S/'case/wind_bc/profile.dat')
(S/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'stage_t5.tar.gz','w:gz') as t:t.add(S,arcname='stage')
(R/'archive.json').write_text(json.dumps({'sha256':sha(R/'stage_t5.tar.gz'),'bytes':(R/'stage_t5.tar.gz').stat().st_size})+'\n')
print(json.dumps({'archive':json.loads((R/'archive.json').read_text()),'cases':manifest['cases'],'sources':manifest['source']},indent=2))
