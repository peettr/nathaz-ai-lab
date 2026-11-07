#!/usr/bin/env python3
"""Correct perfect A2 forecast to include same Guo-style LPF; new run root."""
import json,os,time,subprocess
from pathlib import Path
import numpy as np
import segment_a_run as a,segment_a2_run as old,segment_a2_guo_run as m
from wind_field_probe import CASES
r=m.BASE/'segment_a2_guo_perfect_filtered_v3';assert not r.exists(),'refuse root overwrite';r.mkdir();case=r/'I_near';case.mkdir()
p=json.loads((m.SRC/'I_near/provenance.json').read_text());start,end=p['window_abs'];dt=a.STEP
(case/'wind.wnd').symlink_to(m.SRC/'I_near/wind.wnd')
t=np.arange(start,end+dt/2,dt)
c=next(x for x in CASES if x.name=='I_near')
u,v,_=a.speed(c,0,t);rotor=np.hypot(u,v)
filtered=m.smooth(rotor,dt,.1)
# Ideal forecast provides future rotor wind for time t+Tfilter+Tpitch+Twindow/2.
Tfilter=1/(2*np.pi*.1);series=np.interp(t+Tfilter+.22+.5,t,filtered,right=filtered[-1])
with (case/'perfect.txt').open('w') as f:
 f.write('# time[s] ideal filtered rotor forecast[m/s]\n')
 for tt,wind in zip(t-start,series):f.write(f'{tt:.3f} {wind:.6f}\n')
row=dict(case='I_near',group='perfect',preview='perfect',gain=1,trigger_abs=p['rotor_cross_25_abs']+50,crossing_abs=p['rotor_cross_25_abs'],start=start,end=end,actual_lead_s=-50)
old.ROOT=r;old.LIB=m.LIB;dest=old.stage(row)
env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='1')
t0=time.monotonic()
with (dest/'openfast.log').open('w') as f:
 try:ret=subprocess.run([str(a.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=400).returncode
 except subprocess.TimeoutExpired:ret=-999
result=dict(row,fc_Hz=.1,returncode=ret,wall_s=round(time.monotonic()-t0,3),runroot=str(dest),perfect_formula='LPF(rotor wind) evaluated at t+Tfilter+Tpitch+Twindow/2')
(r/'ledger.jsonl').write_text(json.dumps(result)+'\n');print(result)
