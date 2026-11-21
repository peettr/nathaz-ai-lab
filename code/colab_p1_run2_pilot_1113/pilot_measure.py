#!/usr/bin/env python3
"""Run one full-duration P1 G1 case to measure single-CPU wall time."""
import os, json, time, traceback
from pathlib import Path
os.environ.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENFAST_TIMEOUT_S='2400')
import colab_a170_2 as m
c=Path('/content')
try:
    assert os.cpu_count() >= 1
    m.init()
    p=m.make_seed(1301,'power')
    row=m.row(1301,'power','G1',p['rotor_3s_first25_abs_s'])
    begin=time.monotonic()
    result=m.run_one(row)
    payload={'cpu_count':os.cpu_count(),'parallel':1,'timeout_s':2400,'full_wall_s':time.monotonic()-begin,'result':result,'status':'success'}
    (c/'a170_2_pilot_measure.json').write_text(json.dumps(payload,indent=2))
    m.checkpoint()
    (c/'a170_2_pilot_measure.done').write_text('ok\n')
    print('PILOT_DONE',payload['full_wall_s'],flush=True)
except BaseException:
    tb=traceback.format_exc();(c/'a170_2_pilot_measure.failed').write_text(tb)
    print(tb,flush=True)
    raise
