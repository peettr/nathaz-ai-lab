"""One-shot stage-two launcher on Colab; no automatic retries or hidden skips.
Invoke only after verifying data/code hashes, baseline adapter parity, CU margin
and absence of another stage-two process. Caller supervises each run and archive.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path('/content/v6_work')
# Execution order is conditional: three full seeds must pass the gate;
# then 200 x three seeds; 50/100 only if the pooled-SD RMSE test passes.
ORDER=[('all',42),('all',73)]+[(str(n),seed) for n in (200,50,100) for seed in (17,42,73)]


def run_once(size,seed,run_tag=''):
    assert not run_tag or (size,seed,run_tag)==('all',73,'retry1')
    key=f'v6s2_{size}_seed{seed}' + (f'_{run_tag}' if run_tag else '')
    assert (ROOT/'v6_legacy_code/all_data.pt').stat().st_size==4321275076
    assert (ROOT/'v6_nested_subsets.json').is_file()
    assert not (ROOT/key).exists(),f'run exists; inspect/score-only rather than restart: {key}'
    # The named run creates its own exclusive directory and retains 20 states.
    script=ROOT/'v6s2_run.py'
    assert script.is_file()
    subprocess.run([sys.executable,'-u',str(script),'--size',size,'--seed',str(seed)] +
                   (['--run-tag',run_tag] if run_tag else []),
                   cwd=ROOT,check=True,stdin=subprocess.DEVNULL)
    assert (ROOT/key/'summary.json').is_file()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--size',choices=('50','100','200','all'),required=True)
    p.add_argument('--seed',type=int,choices=(17,42,73),required=True)
    p.add_argument('--run-tag',choices=('retry1',),default='')
    args=p.parse_args()
    assert (args.size,args.seed) in ORDER, 'seed17 all is already complete'
    run_once(args.size,args.seed,args.run_tag)
