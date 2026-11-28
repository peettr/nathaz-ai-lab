#!/usr/bin/env python3
"""Create UGE scripts under a new B0c root; never replace existing scripts."""
from pathlib import Path
import sys
root=Path(sys.argv[1]); assert root.is_dir()
for kind, cores, wall, mem in [('smoke',1,'00:15:00','32G'),('single',1,'02:00:00','32G'),('mpi48',48,'00:20:00','1G')]:
    dest=root/kind
    assert not dest.exists()
    dest.mkdir()
    directives=[f'#$ -N L2624B0c_{kind}', '#$ -q hpc',f'#$ -l h_rt={wall}',f'#$ -l m_mem_free={mem}',"#$ -hard -l hostname='!(d24cepyc154*|d24cepyc161*|d24cepyc162*)'"]
    if cores == 48: directives.append('#$ -pe mpi-48 48')
    directives += ['#$ -cwd','#$ -j y',f'#$ -o {dest}/sge.log']
    text='#!/bin/bash\n'+'\n'.join(directives)+f'''\ncd {dest} || exit 90
trap 'r=$?; printf "%s\\n" "$r" > {dest}/run.exitcode' EXIT
bash {root}/run_B0c_repeat.sh {cores} {'smoke' if kind=='smoke' else 'full'} {dest} > {dest}/log.run 2>&1
'''
    (dest/'job.sh').write_text(text)
    print(dest/'job.sh')
