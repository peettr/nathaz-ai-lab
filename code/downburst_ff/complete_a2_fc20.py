#!/usr/bin/env python3
"""Complete interrupted fc=.20 2D in fresh attempt2 directory only."""
import os,time,json,subprocess
from pathlib import Path
import segment_a_run as a, segment_a2_run as old, segment_a2_guo_run as m
r=Path('./lab_a3/downburst_ff/segment_a2_guo_fc20')
old.ROOT=r;old.LIB=m.LIB
case='I_near';p=json.loads((m.SRC/case/'provenance.json').read_text());start,end=p['window_abs']
row=dict(case=case,group='real_2D',preview='real_2D',gain=1,trigger_abs=p['rotor_cross_25_abs']+50,crossing_abs=p['rotor_cross_25_abs'],start=start,end=end,actual_lead_s=-50)
assert not (r/'run_I_near_real_2D_attempt2').exists()
dest=old.stage(row)
assert dest.name.endswith('_attempt2')
env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='1')
t0=time.monotonic()
with (dest/'openfast.log').open('w') as f:
    try:ret=subprocess.run([str(a.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=400).returncode
    except subprocess.TimeoutExpired:ret=-999
result=dict(row,fc_Hz=.2,returncode=ret,wall_s=round(time.monotonic()-t0,3),runroot=str(dest))
with (r/'ledger.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
print(result)
