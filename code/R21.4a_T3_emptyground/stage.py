#!/usr/bin/env python3
"""Freeze four no-building decks from the archived B2u source, fail closed."""
from pathlib import Path
import tarfile, shutil, hashlib, struct, json, csv, statistics
R=Path(__file__).resolve().parent
B=R.parent/'tacc_feasibility/T2d_a/B2u_inputs.tar.gz'
with tarfile.open(B) as tf:
    for m in tf.getmembers():
        target=(R/'stage'/m.name).resolve()
        assert target.is_relative_to((R/'stage').resolve()) and not m.issym() and not m.islnk()
    (R/'stage').mkdir(exist_ok=False)
    tf.extractall(R/'stage',filter='data')
src=R/'stage/FluidX3D/src'
for n,h in [('setup.cpp','9c5e0d2c0cc5cf129c7dc1b018139e04b70e4e0cac8dc5bb8354d1a0dc33aac1'),('defines.hpp','cb1009f00376f9d9d51114473a6673516be1f594874c1347c08152e3d9448ac3')]:
    p=R/'baseline'/n; assert hashlib.sha256(p.read_bytes()).hexdigest()==h
    shutil.copyfile(p,src/n)
conf=(R/'stage/case/conf.luwpf').read_text(); assert 'vk_inlet_seed' not in conf
# 12-triangle flat box with original x span and -20..0 m elevation, no buildings.
verts=[(0.,0.,-20.),(500.,0.,-20.),(500.,30.,-20.),(0.,30.,-20.),(0.,0.,0.),(500.,0.,0.),(500.,30.,0.),(0.,30.,0.)]
faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
with (R/'stage/flatground.stl').open('xb') as f:
    f.write(b'T3 flat-ground closed box'.ljust(80,b' '));f.write(struct.pack('<I',len(faces)))
    for a,b,c in faces:
        f.write(struct.pack('<12fH',0.,0.,0.,*verts[a],*verts[b],*verts[c],0))
rows=list(csv.DictReader((R.parent/'tacc_feasibility/T2d_a/widths.csv').open()))
wide=[float(r['x_m']) for r in rows if float(r['width_min_m'])>=15]
assert len(wide)==64
xc=statistics.mean(wide)
manifest={'source_B2u_tar_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'setup_sha256':hashlib.sha256((src/'setup.cpp').read_bytes()).hexdigest(),'defines_sha256':hashlib.sha256((src/'defines.hpp').read_bytes()).hexdigest(),'flatground_sha256':hashlib.sha256((R/'stage/flatground.stl').read_bytes()).hexdigest(),'xc_m':xc,'wide_count':len(wide),'center_band_y_m':[10,20],'side_profile_y_m':[2,5,8,10,15,20,22,25,28],'domain_m':[500,30,270],'sponge_m':200,'cases':{}}
for dx in (1.,.5):
    for seed in (101,102):
        name=f'dx{str(dx).replace(".","p")}_s{seed}'
        case=R/'stage'/name
        (case/'wind_bc').mkdir(parents=True)
        (case/'proj_temp').mkdir()
        shutil.copyfile(R/'stage/case/wind_bc/profile.dat',case/'wind_bc/profile.dat')
        shutil.copyfile(R/'stage/flatground.stl',case/'proj_temp/CaseE_PF.stl')
        s=conf
        for old,new in [('si_y_cfd = [0.000000, 500.000000]','si_y_cfd = [0.000000, 30.000000]'),('cell_size = 1.0',f'cell_size = {dx:.1f}'),('run_nstep = 31000',f'run_nstep = {round(31000/dx)}'),('purge_avg = 20000',f'purge_avg = {round(20000/dx)}'),('purge_avg_stride = 40',f'purge_avg_stride = {round(40/dx)}')]:
            assert s.count(old)==1,(name,old)
            s=s.replace(old,new)
        s+=f'\n// T3 empty ground; B2u physical time, seed only realization change\nvk_inlet_seed = {seed}\n'
        (case/'conf.luwpf').write_text(s)
        cells=round(500/dx)*round(30/dx)*round(470/dx)
        manifest['cases'][name]={'dx':dx,'seed':seed,'cells_total':cells,'core_cells':round(500/dx)*round(30/dx)*round(270/dx),'steps':round(31000/dx),'avg_steps':round(20000/dx),'stride':round(40/dx),'conf_sha256':hashlib.sha256(s.encode()).hexdigest()}
(R/'stage_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
