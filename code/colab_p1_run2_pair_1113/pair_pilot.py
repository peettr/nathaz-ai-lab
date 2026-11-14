#!/usr/bin/env python3
"""Measure two complete P1 G1 OpenFAST solves under 2-CPU contention."""
import os, json, time, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
os.environ.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb', OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1', OPENFAST_TIMEOUT_S='2400')
import colab_a170_2 as m
C=Path('/content'); OUT=C/'a170_2_pair_pilot.json'
try:
    assert os.cpu_count()==2, os.cpu_count()
    m.init()
    rows=[]
    for seed in (1301,1302):
        p=m.make_seed(seed,'power')
        rows.append(m.row(seed,'power','G1',p['rotor_3s_first25_abs_s']))
    start=time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures=[ex.submit(m.run_one,r) for r in rows]
        results=[f.result() for f in futures]
    payload={'cpu_count':os.cpu_count(),'parallel':2,'temporary_timeout_s':2400,'pair_wall_s':time.monotonic()-start,'results':results}
    OUT.write_text(json.dumps(payload,indent=2))
    m.checkpoint()
    if any(r['returncode']!=0 for r in results):
        raise RuntimeError('pair solver failed; inspect result JSON and checkpoint')
    (C/'a170_2_pair_pilot.done').write_text('ok\n')
    print('PAIR_PILOT_DONE',payload['pair_wall_s'],[r['wall_s'] for r in results],flush=True)
except BaseException:
    (C/'a170_2_pair_pilot.failed').write_text(traceback.format_exc())
    traceback.print_exc()
    raise
