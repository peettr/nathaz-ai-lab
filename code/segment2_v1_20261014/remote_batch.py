"""Detached idempotent group loop; host watchdog enforces budget and pulls progress."""
import os,sys,traceback,time
from pathlib import Path
P=Path('/content'); log=P/'r2_v1_segment2_batch.log'; done=P/'r2_v1_segment2_batch.done';started=P/'r2_v1_segment2_batch.started'
with started.open('x') as f:f.write(str(os.getpid()))
with log.open('x',buffering=1) as f:
    sys.stdout=f;sys.stderr=f
    try:
        code=(P/'run_v1_segment2_group.py').read_text()
        for i in range(95):
            print('BEGIN_GROUP',i+1,flush=True)
            exec(compile(code,str(P/'run_v1_segment2_group.py'),'exec'),globals())
            print('END_GROUP',i+1,flush=True)
            if not remaining:
                done.write_text('complete\n');break
        else:done.write_text('iteration_limit\n')
    except BaseException:
        traceback.print_exc();done.write_text('error\n')
