#!/usr/bin/env python3
"""A3 deterministic exploratory runs; immutable run roots; see RESULTS_A.md for limits.
Usage: env/bin/python segment_a_run.py prepare|run [--max-runs N]
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time
from dataclasses import replace
from pathlib import Path
import numpy as np
from wind_field_probe import field, CASES, D
HERE=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff/segment_a_v10')
SRC=Path('./lab_a3/downburst_ff/ff_smoke_feedback')
LIB=Path('./lab_a3/downburst_ff/rosco210_ff_build_curve_v1/libdiscon.so')
CURVE=Path('./lab_a3/downburst_ff/segment_a_v4_curve.txt')
FAST=Path('./lab_a3/env/bin/openfast')
STEP=.25
GRID=[(-.6,0), (0,0),(.6,0),(0,-.6),(0,.6),(-.4,-.4),(.4,-.4),(-.4,.4),(.4,.4)]

def speed(case,x,t):
    us=[];vs=[];ws=[]
    for y,zf in GRID:
        u,v,w=field(case,x,y*63,90+zf*63,t)
        us.append(u);vs.append(v);ws.append(w)
    return np.mean(us,axis=0),np.mean(vs,axis=0),np.mean(ws,axis=0)

def threshold(t,s,value):
    ix=np.flatnonzero((s[:-1]<value)&(s[1:]>=value))
    if not len(ix):raise RuntimeError(f'no crossing {value}')
    k=ix[0];return float(t[k]+(value-s[k])/(s[k+1]-s[k])*(t[k+1]-t[k]))

def replace_key(path,key,value):
    s=path.read_text(); pat=r'(?m)^.*?(\s+'+re.escape(key)+r'\s+[^\n]*)$'
    s,n=re.subn(pat,lambda m:f'{value} {m.group(1)}',s,count=1)
    if n!=1:raise RuntimeError(f'{path}: key {key} count {n}')
    path.write_text(s)

def replace_discon(path,key,value):
    s=path.read_text();s,n=re.subn(r'(?m)^.*?(\s+! '+re.escape(key)+r'\b[^\n]*)$',lambda m:f'{value}{m.group(1)}',s,count=1)
    if n!=1:raise RuntimeError(f'{path}: DISCON key {key} count {n}')
    path.write_text(s)

def smooth(x,dt,tau):
    y=np.empty_like(x);y[0]=x[0];a=dt/(tau+dt)
    for k in range(1,len(x)):y[k]=y[k-1]+a*(x[k]-y[k-1])
    return y

def prepare():
    if ROOT.exists():raise RuntimeError(f'refuse existing run root {ROOT}')
    if not all(p.exists() for p in (SRC,LIB,FAST,CURVE)):raise RuntimeError('missing smoke prerequisites')
    ROOT.mkdir(parents=True)
    manifest=[]
    for original in CASES:
        # Correct inherited diagnostic's Case III typo: Nguyen Table 4.4 kzm=0.05 m/s.
        c=replace(original,kzm=.05) if original.name=='III_offset' else original
        full=np.arange(0,1050+STEP/2,STEP)
        uu,vv,ww=speed(c,0,full); mag=np.hypot(uu,vv)
        onset=threshold(full,mag,13.0)
        crossing=threshold(full,mag,25.0)
        beyond=np.flatnonzero((full>crossing)&(mag>=25.0))
        last=full[beyond[-1]]
        start=math.floor((onset-60)/STEP)*STEP
        end=math.ceil((last+60)/STEP)*STEP
        if start<0:raise RuntimeError('initialization impossible')
        t=np.arange(start,end+STEP/2,STEP)
        u,v,w=speed(c,0,t);s=np.hypot(u,v)
        # InflowWind wind direction is meteorological rotation toward -Y.
        wd=-np.degrees(np.arctan2(v,u))
        path=ROOT/c.name;path.mkdir()
        with (path/'wind.wnd').open('w') as f:
            f.write('! Nguyen 2012 analytic field; rotor-plane nine-point mean at x=0; A3 uniform projection\n')
            f.write('! Time  Speed Dir VertSpeed HorizShear VertShear LinVShear Gust Upflow\n')
            for j in range(len(t)):
                f.write(f'{t[j]-start:.3f} {s[j]:.6f} {wd[j]:.6f} {w[j]:.6f} 0.2 0 0 0 0\n')
        # Preview: independent nine-point upwind samples; x-directed LOS proxy,
        # normalized against local direction. Causal 2 s lowpass and 2 s processing lag.
        previews={}
        upstream_raw={}
        for n in (1,2):
            pu,pv,pw=speed(c,-n*D,t)
            upstream_raw[n]=np.hypot(pu,pv)
            # Two-beam idealized LOS reconstruction uses ONLY upstream data.
            # Never divide by rotor direction (that would leak rotor truth).
            upstream_angle_cos=pu/np.maximum(upstream_raw[n],.01)
            los=pu/np.maximum(upstream_angle_cos,.2)
            filtered=smooth(los,STEP,2.0)
            delayed=np.interp(t-2,t,filtered,left=filtered[0])
            previews[n]=delayed
        # Perfect future preview accounts for two-second actuator/processing lead.
        perfect=np.interp(t+2,t,s,right=s[-1])
        # The realistic trigger is not handed the future rotor crossing. At the
        # first filtered upstream threshold, estimate transport from that same
        # measured speed and the x-separated probe; detection carries delay.
        upstream_detect=threshold(t,previews[1],25.0)
        up_speed=float(np.interp(upstream_detect,t,upstream_raw[1]))
        predicted_cross=upstream_detect+D/up_speed
        # Arrival-based 50 s protection: scheduled from rotor threshold, with no forecast for 0.
        base=crossing+50
        for group in ['feedback','perfect','real_1D','real_2D']:
            manifest.append(dict(case=c.name,group=group,stop_T=None,trigger_abs=base,
                                 gain=0 if group=='feedback' else 1.0,preview=group,start=start,end=end,
                                 crossing_abs=crossing))
        for quality in ['perfect','real_1D']:
            for advance in (0,5,10,20,40):
                trigger=base if advance==0 else (crossing-advance if quality=='perfect' else max(upstream_detect,predicted_cross-advance))
                manifest.append(dict(case=c.name,group=f'stop_{quality}_{advance}',stop_T=advance,
                                     trigger_abs=trigger,gain=0,preview=quality,start=start,end=end,
                                     crossing_abs=crossing,predicted_cross_abs=predicted_cross))
        for quality,series in [('feedback',s),('perfect',perfect),('real_1D',previews[1]),('real_2D',previews[2])]:
            with (path/f'{quality}.txt').open('w') as f:
                f.write('# t_since_window_start[s]  preview_horizontal[m/s]\n')
                for a,b in zip(t-start,series):f.write(f'{a:.3f} {b:.6f}\n')
        (path/'provenance.json').write_text(json.dumps({'Nguyen_case':vars(c),'onset_13_abs':onset,
            'rotor_cross_25_abs':crossing,'last_25_abs':float(last),'window_abs':[start,end],
            'rotor_approx':'9-point disk average of 4D analytic field; uniform projection',
            'preview':'9-point x-upstream independently sampled; idealized two-beam local-direction LOS reconstruction; first-order 2s filter plus 2s delay',
            'realistic_upstream_detection_abs':upstream_detect,'upwind_measured_speed_mps':up_speed,
            'realistic_predicted_rotor_cross_abs':predicted_cross,
            'perfect':'rotor 9-point average shifted +2s; no future info available to realistic condition'},indent=2)+'\n')
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('prepared',len(manifest),'runs',[(c.name,(ROOT/c.name/'provenance.json').read_text()[:190]) for c in CASES])

def stage(row):
    case=ROOT/row['case'];dest=ROOT/('run_'+row['case']+'_'+row['group'])
    if dest.exists():raise RuntimeError(f'refuse existing case {dest}')
    shutil.copytree(SRC,dest,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.wnd','preview.txt'))
    # Original Cp/Ct/Cq table is included in the copied case tree.
    assert (dest/'Cp_Ct_Cq.NREL5MW.txt').exists()
    (dest/'wind.wnd').symlink_to(case/'wind.wnd')
    (dest/'preview.txt').symlink_to(case/f'{row["preview"]}.txt')
    replace_key(dest/'NREL-5MW.fst','TMax',f'{row["end"]-row["start"]:.3f}')
    replace_key(dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat','DLL_FileName',f'"{LIB}"')
    replace_key(dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat','YCMode','5')
    ed=dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
    ed_text=ed.read_text();needle='END of input file (the word "END" must appear in the first 3 columns of this last OutList line)'
    assert ed_text.count(needle)==1
    ed.write_text(ed_text.replace(needle,'"NacYaw" - measured nacelle yaw\n'+needle))
    inflow=dest/'NRELOffshrBsline5MW_InflowWind.dat'
    replace_key(inflow,'WindType','2')
    replace_key(inflow,'Filename_Uni','"wind.wnd"')
    replace_key(inflow,'RefHt_Uni','90')
    cfg=dest/'DISCON.IN'
    replace_discon(cfg,'Y_ControlMode','1')
    replace_discon(cfg,'Y_Rate',f'{math.radians(.3):.10f}')
    replace_discon(cfg,'PC_MaxRat',f'{math.radians(8):.10f}')
    replace_discon(cfg,'PC_MinRat',f'{-math.radians(8):.10f}')
    replace_discon(cfg,'SD_EnableTime','1')
    replace_discon(cfg,'SD_Mode','1')
    replace_discon(cfg,'SD_Time',f'{row["trigger_abs"]-row["start"]:.6f}')
    replace_discon(cfg,'SD_MaxPitchRate',f'{math.radians(8):.10f}')
    return dest

def run(max_runs,case_filter,group_filter):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    ledger=ROOT/'ledger.jsonl';done=set()
    if ledger.exists():
        done={o['case']+'_'+o['group'] for o in map(json.loads,ledger.read_text().splitlines())}
    count=0
    for row in manifest:
        if case_filter and row['case']!=case_filter:continue
        if group_filter and row['group'] not in group_filter:continue
        key=row['case']+'_'+row['group']
        if key in done:continue
        if count>=max_runs:break
        # Conservative wall-clock budget includes stage and analysis, never launch beyond 3h.
        if time.time()-float((ROOT/'started_epoch.txt').read_text())>2.9*3600:
            print('STOP: 3h budget guard',flush=True);break
        runroot=stage(row)
        env=os.environ.copy();env.update(ROSCO_FF_FILE=str(runroot/'preview.txt'),ROSCO_FF_CURVE=str(CURVE),ROSCO_FF_GAIN_DEG_PER_MS=str(row['gain']))
        t0=time.monotonic()
        with (runroot/'openfast.log').open('w') as log:
            try:
                cp=subprocess.run([str(FAST),'NREL-5MW.fst'],cwd=runroot,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=650)
                rc=cp.returncode
            except subprocess.TimeoutExpired:rc=-999
        result=dict(row,returncode=rc,elapsed_s=round(time.monotonic()-t0,3),runroot=str(runroot))
        with ledger.open('a') as f:f.write(json.dumps(result)+'\n')
        print(key,rc,result['elapsed_s'],flush=True)
        count+=1
        if rc!=0:print('STOP: failed case; inspect log',flush=True);break

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--max-runs',type=int,default=28);p.add_argument('--case',default=None);p.add_argument('--groups',default='');a=p.parse_args()
    if a.command=='prepare':prepare()
    else:run(a.max_runs,a.case,set(a.groups.split(',')) if a.groups else None)
