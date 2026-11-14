#!/usr/bin/env python3
"""Stage two fresh T2d seed-only variants, without modifying T2d-a."""
import hashlib
import pathlib
import shutil
import sys

old = pathlib.Path('/scratch/04448/[用户]/r24_luw/T2d_a_v2')
for seed in (102, 103):
    root = pathlib.Path(f'/scratch/04448/[用户]/r24_luw/T2d_a3_s{seed}')
    root.mkdir(exist_ok=False)
    shutil.copytree(old/'FluidX3D', root/'FluidX3D', ignore=shutil.ignore_patterns('*.o', 'FluidX3D', 'bin'))
    case = root/'case_4gpu'
    case.mkdir()
    for rel in ('wind_bc/profile.dat', 'proj_temp/CaseE_PF.stl'):
        (case/rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old/'case_4gpu'/rel, case/rel)
    conf = (old/'case_4gpu/conf.luwpf').read_text()
    assert conf.count('vk_inlet_seed = 101') == 1
    (case/'conf.luwpf').write_text(conf.replace('vk_inlet_seed = 101', f'vk_inlet_seed = {seed}'))
    for name in ('drive_t2b.py', 'post_t2d.py', 'post_t2.py', 'B2u_reference_points.json', 'widths.csv'):
        shutil.copy2(old/name, root/name)
    run = (old/'run_t2d.sh').read_text()
    assert run.count('ROOT=/scratch/04448/[用户]/r24_luw/T2d_a_v2') == 1
    run = run.replace('#SBATCH -J LUW_T2d_a', f'#SBATCH -J LUW_T2d_s{seed}')
    run = run.replace('ROOT=/scratch/04448/[用户]/r24_luw/T2d_a_v2', f'ROOT={root}')
    (root/'run_t2d.sh').write_text(run)
    for rel in ('FluidX3D/src/setup.cpp', 'FluidX3D/src/defines.hpp', 'case_4gpu/conf.luwpf', 'case_4gpu/wind_bc/profile.dat', 'case_4gpu/proj_temp/CaseE_PF.stl', 'run_t2d.sh', 'drive_t2b.py', 'post_t2d.py', 'post_t2.py', 'B2u_reference_points.json', 'widths.csv'):
        p = root/rel
        print(seed, rel, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest(), flush=True)
