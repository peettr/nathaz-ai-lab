#!/usr/bin/env python3
"""Create four isolated scheduler wrappers; no submissions."""
from pathlib import Path
base=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/B0')
for n in (1,48):
 for tier in ('ta','tb'):
  name=f'{tier}_n{n}'
  root=base/name
  assert not root.exists()
  root.mkdir()
  pe='#$ -pe mpi-48 48\n' if n==48 else ''
  limit='00:10:00' if n==48 else '04:00:00'
  memory='1G' if n==48 else '32G'
  script=f'''#!/bin/bash
#$ -N L2624B0_{tier}{n}
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
bash {base}/run_B0_variant.sh {tier} {n} {root} > {root}/log.run 2>&1
'''
  (root/'job.sh').write_text(script)
  print(root/'job.sh')
