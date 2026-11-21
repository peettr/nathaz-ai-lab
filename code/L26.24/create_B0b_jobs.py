#!/usr/bin/env python3
"""Generate isolated B0b wrappers; never submit."""
from pathlib import Path
base=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B0b')
for tier,n in [('smoke',1),('ta',1),('tb',1),('ta',48),('tb',48)]:
    root=base/f'{tier}_n{n}'
    assert not root.exists()
    root.mkdir()
    pe='#$ -pe mpi-48 48\n' if n==48 else ''
    limit='00:10:00' if n==48 else ('00:15:00' if tier=='smoke' else '04:00:00')
    memory='1G' if n==48 else '32G'
    script=f'''#!/bin/bash
#$ -N L2624B0b_{tier}{n}
#$ -q hpc
{pe}#$ -l h_rt={limit}
#$ -l m_mem_free={memory}
#$ -hard -l hostname='!(d24cepyc154*|d24cepyc161*|d24cepyc162*)'
#$ -cwd
#$ -j y
#$ -o {root}/sge.log
cd {root} || exit 90
trap 'r=$?; printf "%s\\n" "$r" > {root}/run.exitcode' EXIT
if [ {n} -eq 48 ]; then
  test -n "${{PE_HOSTFILE:-}}" || exit 97
  test "$(cut -d' ' -f1 "$PE_HOSTFILE" | sort -u | wc -l)" -eq 1 || exit 98
fi
bash {base}/run_B0b_variant.sh {tier} {n} {root} > {root}/log.run 2>&1
'''
    (root/'job.sh').write_text(script)
    print(root/'job.sh')
