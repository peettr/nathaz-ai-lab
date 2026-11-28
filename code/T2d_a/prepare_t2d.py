#!/usr/bin/env python3
"""T2d-a: immutable B2u archive, corrected inlet mapping, seed-only contrast."""
import pathlib, sys, tarfile, hashlib, shutil
r=pathlib.Path(sys.argv[1]).resolve()
with tarfile.open(r/'B2u_inputs.tar.gz') as tf:
    for member in tf.getmembers():
        target=(r/member.name).resolve()
        if not target.is_relative_to(r) or member.issym() or member.islnk():
            raise RuntimeError(member.name)
    tf.extractall(r,filter='data')
# T1c4 is the exact compiled four-card mother: keep its diagnostic monitor and defines.
# Copy only the source files differing from the B2u archive, without touching T1c4.
mother=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/FluidX3D/src')
setup=r/'FluidX3D/src/setup.cpp'
for name in ('setup.cpp','defines.hpp'):
    shutil.copyfile(mother/name,r/'FluidX3D/src'/name)
s=setup.read_text()
anchor='struct VkInletRuntimeConfig {\n    bool enable = true;'
old='    int nmodes = k_vk_nmodes_default;\n    ulong seed = 100ull;\n    int update_stride = 1;'
assert s.count(anchor)==1 and s.count(old)==2
head,tail=s.split(anchor)
assert tail.count(old)==1
tail=tail.replace(old,'    int nmodes = k_vk_nmodes_default;\n    ulong seed = 100ull;\n    float ground_z_lbm = 20.0f;\n    float cell_size_m = 1.0f;\n    int update_stride = 1;',1)
s=head+anchor+tail
old='                const float z_agl = std::max(0.0f,p.z - 20.0f);'
assert s.count(old)==1
s=s.replace(old,'                const float z_agl = std::max(0.0f, (p.z - cfg_.ground_z_lbm) * cfg_.cell_size_m);')
old='        cfg.seed = vk_inlet_settings.seed;'
assert s.count(old)==1
s=s.replace(old,old+'\n        cfg.ground_z_lbm = units.x(z_si_offset);\n        cfg.cell_size_m = 1.0f / units.x(1.0f);')
setup.write_text(s)
conf=(r/'case/conf.luwpf').read_text()
assert 'cell_size = 1.0' in conf and 'run_nstep = 31000' in conf and 'vk_inlet_l = 100.0' in conf
assert 'vk_inlet_seed' not in conf
conf+='\n// T2d-a: sole inlet realization change relative to T1c4 seed 100\nvk_inlet_seed = 101\n'
case=r/'case_4gpu';case.mkdir(exist_ok=False)
for rel in ('wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):
    (case/rel).parent.mkdir(exist_ok=True)
    shutil.copyfile(r/'case'/rel,case/rel)
assert conf.count('n_gpu = [1, 1, 1]')==1
conf=conf.replace('n_gpu = [1, 1, 1]','n_gpu = [4, 1, 1]')
(case/'conf.luwpf').write_text(conf)
for p in (setup,case/'conf.luwpf',case/'wind_bc/profile.dat',case/'proj_temp/CaseE_PF.stl'):
    print('INPUT',p.relative_to(r),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
