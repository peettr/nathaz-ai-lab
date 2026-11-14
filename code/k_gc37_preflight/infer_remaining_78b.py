#!/usr/bin/env python3
"""Resume only unrun P48/P72 preparation, QA and inference; never replay P24."""
from pathlib import Path
import datetime, subprocess, traceback
R=Path('/content/r234c_gc37_78b7088f')
LOG=R/'infer_remaining_78b.log'
def say(*args):
    with LOG.open('a') as f:
        print(datetime.datetime.now().isoformat(), *args, file=f, flush=True)
def stage(name, argv):
    path=R/(name+'_remaining.log')
    say('START',name,argv)
    with path.open('x') as f:
        rc=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT).returncode
    say('END',name,rc)
    if rc: raise RuntimeError((name,rc))
try:
    for cycle,steps in [('2020060706',9),('2020060606',13)]:
        if (R/f'input_{cycle}_zero.nc').exists() or (R/f'forecast_{cycle}_full_{steps}step').exists():
            raise FileExistsError('Refusing replay of '+cycle)
        stage('prepare_'+cycle,['python3','/content/prepare_gc37_gfs.py','--cycle',cycle,'--case','zero','--root',str(R)])
        stage('qa_t0_'+cycle,['python3','/content/qa_t0_gfs.py','--cycle',cycle,'--root',str(R)])
        stage('infer_'+cycle,['python3','/content/run_gc37_full.py','--cycle',cycle,'--case','zero','--run-tag','full','--steps',str(steps),'--root',str(R)])
    (R/'infer_remaining_78b.done').write_text('SUCCESS_P48_P72\n')
    say('SUCCESS')
except Exception as e:
    say('FAILED',repr(e),traceback.format_exc())
    (R/'infer_remaining_78b.failed').write_text(repr(e)+'\n')
    raise
