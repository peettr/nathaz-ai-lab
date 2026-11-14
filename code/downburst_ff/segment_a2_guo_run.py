#!/usr/bin/env python3
"""A2 amended Guo-inspired law; immutable v2 roots, no old results touched."""
import json, math, os, shutil, subprocess, time, sys
from pathlib import Path
import numpy as np
import segment_a_run as a
import segment_a2_run as old
BASE=Path('./lab_a3/downburst_ff')
ROOT=BASE/'segment_a2_guo_v2'
SRC=BASE/'segment_a_v10'
LIB=BASE/'rosco210_ff_build_guo_v2/libdiscon.so'
FC=float(os.environ.get('A3_FC','0.10')) # Hz: assumed, 0.05/0.10/0.20 sensitivity
# 2h cumulative solver time, including earlier A2 1747.025 s; conservative guard.
PREVIOUS=1747.025

def smooth(x,dt,fc):
    y=np.empty_like(x);y[0]=x[0];alpha=1-math.exp(-2*math.pi*fc*dt)
    for i in range(1,len(x)):y[i]=y[i-1]+alpha*(x[i]-y[i-1])
    return y

def prepare():
    assert not ROOT.exists(), 'refuse existing root'
    assert LIB.exists(), 'build library first'
    ROOT.mkdir()
    rows=[]
    for case in ('I_near',): # Case III existing yaw gate fails; do not simulate invalid load.
        p=json.loads((SRC/case/'provenance.json').read_text()); start,end=p['window_abs']
        dest=ROOT/case;dest.mkdir()
        for fn in ('wind.wnd','provenance.json'): (dest/fn).symlink_to(SRC/case/fn)
        from dataclasses import replace
        from wind_field_probe import CASES,D
        c=next(z for z in CASES if z.name==case)
        t=np.arange(start,end+a.STEP/2,a.STEP)
        rotor_u,rotor_v,_=a.speed(c,0,t);rotor=np.hypot(rotor_u,rotor_v)
        for quality in ('feedback','perfect','real_1D','real_2D'):
            if quality=='feedback': series=rotor.copy()
            elif quality=='perfect':
                # Ideal rotor forecast with lead for pitch and half-window, no upstream coherence loss.
                series=np.interp(t+.22+.5,t,rotor,right=rotor[-1])
            else:
                n=1 if quality=='real_1D' else 2
                u,v,_=a.speed(c,-n*D,t);raw=np.hypot(u,v)
                filt=smooth(raw,a.STEP,FC)
                # Tlead measured locally (nine-point upstream), causal bound on use of samples.
                lead=n*D/np.maximum(raw,1)
                tfilt=1/(2*math.pi*FC)
                buffer=np.maximum(0,lead-tfilt-.22-.5)
                # Input time t observes only filtered upstream measurements as of t-buffer.
                series=np.interp(t-buffer,t,filt,left=filt[0])
                (dest/f'{quality}_timing.json').write_text(json.dumps(dict(fc_Hz=FC,Tfilter_s=tfilt,Tpitch_s=.22,Twindow_s=1.,lead_range_s=[float(lead.min()),float(lead.max())],buffer_range_s=[float(buffer.min()),float(buffer.max())],clamped_fraction=float(np.mean(buffer==0))),indent=2))
            with (dest/f'{quality}.txt').open('w') as f:
                f.write('# t_since_start[s] u_preview[m/s]; source Nguyen 2012 analytic field\n')
                for tt,uu in zip(t-start,series):f.write(f'{tt:.3f} {uu:.6f}\n')
        cross=p['rotor_cross_25_abs'];detect=p['realistic_upstream_detection_abs'];pred=p['realistic_predicted_rotor_cross_abs']
        specs=[('feedback','feedback',0,cross+50),('instant','feedback',0,cross),('perfect','perfect',1,cross+50),('real_1D','real_1D',1,cross+50),('real_2D','real_2D',1,cross+50)]
        specs += [(f'stop_perfect_{T}','perfect',0,cross-T) for T in (5,10,20,40)]
        specs += [('stop_real_1D','real_1D',0,max(detect,pred-40))]
        rows += [dict(case=case,group=g,preview=q,gain=k,trigger_abs=s,crossing_abs=cross,start=start,end=end,actual_lead_s=cross-s) for g,q,k,s in specs]
    (ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('prepared',len(rows),ROOT)

def run():
    assert ROOT.exists() and LIB.exists()
    old.ROOT=ROOT;old.LIB=LIB
    ledger=ROOT/'ledger.jsonl'
    rows=json.loads((ROOT/'manifest.json').read_text())
    done={z['group'] for z in map(json.loads,ledger.read_text().splitlines())} if ledger.exists() else set()
    for r in rows:
        if r['group'] in done:continue
        spent=PREVIOUS+sum(z['wall_s'] for z in map(json.loads,ledger.read_text().splitlines())) if ledger.exists() else PREVIOUS
        if spent+400>=7200: print('STOP 2h cumulative solver gate',spent,flush=True);break
        dest=old.stage(r)
        env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS=str(r['gain']))
        t0=time.monotonic()
        with (dest/'openfast.log').open('w') as f:
            try: ret=subprocess.run([str(a.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=400).returncode
            except subprocess.TimeoutExpired:ret=-999
        result=dict(r,runroot=str(dest),returncode=ret,wall_s=round(time.monotonic()-t0,3),fc_Hz=FC)
        with ledger.open('a') as f:f.write(json.dumps(result)+'\n')
        print(r['group'],ret,result['wall_s'],flush=True)
        if ret!=0:break
if __name__=='__main__':
    {'prepare':prepare,'run':run}[sys.argv[1]]()
