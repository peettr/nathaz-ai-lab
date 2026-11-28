#!/usr/bin/env python3
"""Stage fresh B0b inputs; never modify immutable source cases."""
import argparse
import os
import shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--t0',type=Path,required=True)
p.add_argument('--s2',type=Path,required=True)
p.add_argument('--parallel',action='store_true')
p.add_argument('--smoke',action='store_true')
a=p.parse_args()
assert not a.root.exists() and a.root.parent.is_dir()
assert a.t0.is_dir() and a.s2.is_dir()
a.root.mkdir()
for stage,source in [('t0',a.t0)] if a.smoke else [('t0',a.t0),('later',a.s2)]:
    target=a.root/stage
    target.mkdir()
    shutil.copytree(source/'system',target/'system')
    shutil.copytree(source/'constant',target/'constant',symlinks=True,
        ignore=shutil.ignore_patterns('polyMesh','triSurface','extendedFeatureEdgeMesh'))
    assert (target/'constant/boundaryData/inlet/points').is_file()
    os.symlink((source/'constant/polyMesh').resolve(),target/'constant/polyMesh',target_is_directory=True)
    initial='0' if stage=='t0' else '44'
    if a.parallel and stage=='later':
        src=Path('/groups/kareem/[用户]/petw_runs/ubwp/r25_2_chew/S2_coarse/production/case')
        for i in range(48):
            cp=target/f'processor{i}'
            cp.mkdir()
            (cp/'constant').mkdir()
            os.symlink((src/f'processor{i}/constant/polyMesh').resolve(),cp/'constant/polyMesh',target_is_directory=True)
            os.symlink((target/'constant/boundaryData').resolve(),cp/'constant/boundaryData',target_is_directory=True)
            os.symlink((src/f'processor{i}/44').resolve(),cp/'44',target_is_directory=True)
    else:
        os.symlink((source/initial).resolve(),target/initial,target_is_directory=True)
print(a.root)
