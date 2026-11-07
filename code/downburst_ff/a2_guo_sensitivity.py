#!/usr/bin/env python3
"""Frequency sensitivity for realistic 1D/2D A2 preview; new immutable roots."""
import json,math,os,sys,time,subprocess
from pathlib import Path
import numpy as np
import segment_a_run as a
import segment_a2_run as old
import segment_a2_guo_run as main
from wind_field_probe import CASES,D
BASE=main.BASE
fc=float(sys.argv[1]);assert fc in (.05,.20)
ROOT=BASE/f'segment_a2_guo_fc{int(fc*100):02d}'
assert not ROOT.exists(),'refuse existing sensitivity root'
ROOT.mkdir()
case=ROOT/'I_near';case.mkdir()
p=json.loads((main.SRC/'I_near/provenance.json').read_text());start,end=p['window_abs']
(case/'wind.wnd').symlink_to(main.SRC/'I_near/wind.wnd')
c=next(q for q in CASES if q.name=='I_near')
t=np.arange(start,end+a.STEP/2,a.STEP)
rows=[]
for n in (1,2):
    u,v,_=a.speed(c,-n*D,t);raw=np.hypot(u,v)
    filt=main.smooth(raw,a.STEP,fc)
    lead=n*D/np.maximum(raw,1);tfilt=1/(2*math.pi*fc)
    buf=np.maximum(0,lead-tfilt-.22-.5)
    series=np.interp(t-buf,t,filt,left=filt[0])
    name=f'real_{n}D'
    with (case/f'{name}.txt').open('w') as f:
        f.write('# time[s] preview[m/s]\n')
        for tt,wind in zip(t-start,series): f.write(f'{tt:.3f} {wind:.6f}\n')
    r=dict(case='I_near',group=name,preview=name,gain=1,trigger_abs=p['rotor_cross_25_abs']+50,crossing_abs=p['rotor_cross_25_abs'],start=start,end=end,actual_lead_s=-50)
    rows.append(r)
(case/'timing.json').write_text(json.dumps(dict(fc_Hz=fc,Tfilter_s=tfilt,Tpitch_s=.22,Twindow_s=1),indent=2))
old.ROOT=ROOT;old.LIB=main.LIB
with (ROOT/'ledger.jsonl').open('w') as ledger:
    for r in rows:
        dest=old.stage(r)
        env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='1')
        t0=time.monotonic()
        with (dest/'openfast.log').open('w') as f:
            try:ret=subprocess.run([str(a.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=400).returncode
            except subprocess.TimeoutExpired:ret=-999
        row=dict(r,fc_Hz=fc,returncode=ret,wall_s=round(time.monotonic()-t0,3),runroot=str(dest))
        ledger.write(json.dumps(row)+'\n');ledger.flush()
        print(fc,r['group'],ret,row['wall_s'],flush=True)
        if ret!=0:break
