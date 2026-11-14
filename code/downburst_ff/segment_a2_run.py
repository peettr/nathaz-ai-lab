#!/usr/bin/env python3
"""A3 A2 immutable local CPU cases; source A inputs are read-only."""
import sys, json, shutil, math, os, subprocess, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import segment_a_run as a
SRCROOT=Path('./lab_a3/downburst_ff/segment_a_v10')
ROOT=Path('./lab_a3/downburst_ff/segment_a2_v1')
BASE=Path('./lab_a3/downburst_ff/ff_smoke_feedback')
LIB=a.LIB
FAST=a.FAST
CURVE=a.CURVE

def prepare():
    if ROOT.exists(): raise RuntimeError('refuse existing A2 root')
    ROOT.mkdir()
    rows=[]
    for case in ('I_near','III_offset'):
        src=SRCROOT/case; dst=ROOT/case;dst.mkdir()
        for name in ('wind.wnd','feedback.txt','perfect.txt','real_1D.txt','real_2D.txt','provenance.json'):
            (dst/name).symlink_to(src/name)
        p=json.loads((src/'provenance.json').read_text())
        cross=p['rotor_cross_25_abs']; start,end=p['window_abs']
        detect=p['realistic_upstream_detection_abs']; pred=p['realistic_predicted_rotor_cross_abs']
        # T=0 waits 50 s; instant uses threshold crossing without preview.
        specs=[('feedback','feedback',0,cross+50),('instant','feedback',0,cross),
               ('perfect','perfect',1,cross+50),('real_1D','real_1D',1,cross+50),
               ('real_2D','real_2D',1,cross+50)]
        specs += [(f'stop_perfect_{t}','perfect',0,cross-t) for t in (5,10,20,40)]
        specs += [('stop_real_1D','real_1D',0,max(detect,pred-40))]
        for group,preview,gain,trigger in specs:
            rows.append(dict(case=case,group=group,preview=preview,gain=gain,trigger_abs=trigger,
                             crossing_abs=cross,start=start,end=end,actual_lead_s=cross-trigger))
    (ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('prepared',len(rows),ROOT)

def stage(r):
    dest=ROOT/('run_'+r['case']+'_'+r['group'])
    if dest.exists():
        dest=ROOT/('run_'+r['case']+'_'+r['group']+'_attempt2')
        if dest.exists():raise RuntimeError(f'refuse existing {dest}')
    shutil.copytree(BASE,dest,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.wnd','preview.txt'))
    (dest/'wind.wnd').symlink_to(ROOT/r['case']/'wind.wnd')
    (dest/'preview.txt').symlink_to(ROOT/r['case']/(r['preview']+'.txt'))
    a.replace_key(dest/'NREL-5MW.fst','TMax',f"{r['end']-r['start']:.3f}")
    sd=dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat'
    a.replace_key(sd,'DLL_FileName',f'"{LIB}"')
    a.replace_key(sd,'YCMode','5')
    a.replace_key(sd,'TYCOn','0.0') # A v10 default 9999.9 disables actuator despite YCMode=5.
    # The yaw DOF is already True. Retain physical spring/damping identical across groups.
    ed=dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
    assert 'True          YawDOF' in ed.read_text()
    needle='END of input file (the word "END" must appear in the first 3 columns of this last OutList line)'
    text=ed.read_text();assert text.count(needle)==1
    ed.write_text(text.replace(needle,'"NacYaw" - measured yaw\n'+needle))
    inflow=dest/'NRELOffshrBsline5MW_InflowWind.dat'
    a.replace_key(inflow,'WindType','2');a.replace_key(inflow,'Filename_Uni','"wind.wnd"');a.replace_key(inflow,'RefHt_Uni','90')
    cfg=dest/'DISCON.IN'
    for key,val in [('Y_ControlMode','1'),('Y_Rate',f'{math.radians(.3):.10f}'),
       ('PC_MaxRat',f'{math.radians(8):.10f}'),('PC_MinRat',f'{-math.radians(8):.10f}'),
       ('SD_EnableTime','1'),('SD_Mode','1'),('SD_Time',f"{r['trigger_abs']-r['start']:.6f}"),
       ('SD_MaxPitchRate',f'{math.radians(8):.10f}')]:a.replace_discon(cfg,key,val)
    return dest

def run():
    rows=json.loads((ROOT/'manifest.json').read_text()); ledger=ROOT/'ledger.jsonl'
    done={x['case']+'_'+x['group'] for x in map(json.loads,ledger.read_text().splitlines())} if ledger.exists() else set()
    # Pilot Case III feedback first; order is locked for provenance.
    rows.sort(key=lambda r: (0 if (r['case'],r['group'])==('III_offset','feedback') else 1,r['case'],r['group']))
    for r in rows:
        key=r['case']+'_'+r['group']
        if key in done:continue
        elapsed=sum(x['wall_s'] for x in map(json.loads,ledger.read_text().splitlines())) if ledger.exists() else 0
        if elapsed+400>=7200:
            print('STOP: conservative 2h solver budget',elapsed,flush=True);break
        dest=stage(r);env=os.environ.copy()
        env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(CURVE),ROSCO_FF_GAIN_DEG_PER_MS=str(r['gain']))
        t0=time.monotonic()
        with (dest/'openfast.log').open('w') as f:
            try:ret=subprocess.run([str(FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=400).returncode
            except subprocess.TimeoutExpired:ret=-999
        row=dict(r,runroot=str(dest),returncode=ret,wall_s=round(time.monotonic()-t0,3))
        with ledger.open('a') as f:f.write(json.dumps(row)+'\n')
        print(key,ret,row['wall_s'],flush=True)
        if ret!=0:break
        if key=='III_offset_feedback':
            import numpy as np
            out=dest/'NREL-5MW.out';cols=out.read_text().splitlines()[6].split()
            v=np.loadtxt(out,skiprows=8,usecols=[cols.index(x) for x in ['Time','NacYaw','Wind1VelX','Wind1VelY']]);
            print('YAW PILOT',v[:,1].min(),v[:,1].max(), 'wind',np.degrees(np.arctan2(v[:,3],v[:,2])).min(),np.degrees(np.arctan2(v[:,3],v[:,2])).max(),flush=True)
            if np.ptp(v[:,1])<10: print('STOP: yaw pilot did not follow; no sweep',flush=True);break
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
