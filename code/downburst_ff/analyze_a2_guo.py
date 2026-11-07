#!/usr/bin/env python3
"""Analyze immutable amended A2 near-center runs; no invalid Case III loads."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff/segment_a2_guo_v2')
DEST=HERE/'metrics_A2_guo_v2.json'
PLOTS=[HERE/'timeseries_A2_guo_I_near.png',HERE/'stop_scan_A2_guo_I_near.png']
assert not DEST.exists() and not any(p.exists() for p in PLOTS),'refuse overwrite'
ledger=[json.loads(s) for s in (ROOT/'ledger.jsonl').read_text().splitlines()]
manifest=json.loads((ROOT/'manifest.json').read_text())
p=json.loads((ROOT/'I_near/provenance.json').read_text())
fields=['Time','Wind1VelX','Wind1VelY','BldPitch1','RotSpeed','RootMyb1','YawBrMzp','TwrBsMxt','TwrBsMyt','NacYaw']
runs=[];by={}
for r in ledger:
    if r['returncode']!=0:continue
    f=Path(r['runroot'])/'NREL-5MW.out'
    with f.open() as fh:
        for i,line in enumerate(fh):
            if i==6:cols=line.split();break
    v=np.loadtxt(f,skiprows=8,usecols=[cols.index(x) for x in fields]);d=dict(zip(fields,v.T))
    assert abs(d['Time'][-1]-(r['end']-r['start']))<.1,(f,'incomplete')
    by[r['group']]=d
    masks={'full':d['Time']>=60,'event':(d['Time']>=p['onset_13_abs']-r['start'])&(d['Time']<=p['last_25_abs']-r['start']+60)}
    scopes={}
    for label,mask in masks.items():
        q=lambda k:d[k][mask]; rpm=q('RotSpeed')
        scopes[label]=dict(tower_resultant_max_kNm=float(np.hypot(q('TwrBsMxt'),q('TwrBsMyt')).max()),
          tower_fore_aft_absmax_kNm=float(np.abs(q('TwrBsMyt')).max()),tower_fore_aft_positive_max_kNm=float(q('TwrBsMyt').max()),tower_fore_aft_negative_min_kNm=float(q('TwrBsMyt').min()),tower_side_side_absmax_kNm=float(np.abs(q('TwrBsMxt')).max()),
          tower_top_yaw_absmax_kNm=float(np.abs(q('YawBrMzp')).max()),blade1_root_flapwise_positive_max_kNm=float(q('RootMyb1').max()),blade1_root_flapwise_negative_min_kNm=float(q('RootMyb1').min()),
          rotor_speed_peak_rpm=float(rpm.max()),rotor_speed_overshoot_vs_12p1_pct=float((rpm.max()/12.1-1)*100),blade_pitch_peak_deg=float(q('BldPitch1').max()))
    runs.append(dict(group=r['group'],wall_s=r['wall_s'],actual_lead_s=r['actual_lead_s'],runroot=r['runroot'],metrics=scopes))
lookup={r['group']:r for r in runs}
keys=[k for k in next(iter(lookup.values()))['metrics']['event'] if k not in ('rotor_speed_peak_rpm','blade_pitch_peak_deg')]
ratios=[]
for window in ('full','event'):
    for base,perfect,real,kind in [('feedback','perfect','real_1D','pitch_1D'),('feedback','perfect','real_2D','pitch_2D')]+[('instant',f'stop_perfect_{t}','stop_real_1D',f'stop_T{t}_real_1D') for t in (5,10,20,40)]:
        for k in keys:
            if any(g not in lookup for g in (base,perfect,real)):
                ratios.append(dict(window=window,kind=kind,metric=k,ratio=None,status='missing'));continue
            vals=[lookup[g]['metrics'][window][k] for g in (base,perfect,real)]
            if k.endswith('negative_min_kNm'):vals=[-x for x in vals]
            b,f,q=vals;improve=b-f
            valid=improve>0 and improve>.01*abs(b)
            ratios.append(dict(window=window,kind=kind,metric=k,ratio=(b-q)/improve if valid else None,status='valid' if valid else 'not_applicable_under_1pct',baseline=b,perfect=f,real=q))
fig,axes=plt.subplots(5,1,figsize=(10,11),sharex=True)
for group in ('feedback','instant','perfect','real_1D','real_2D'):
    d=by.get(group)
    if d is None:continue
    t=d['Time'];axes[0].plot(t,np.hypot(d['Wind1VelX'],d['Wind1VelY']),label=group,lw=1)
    axes[1].plot(t,np.degrees(np.arctan2(d['Wind1VelY'],d['Wind1VelX'])),lw=1)
    axes[2].plot(t,d['NacYaw'],lw=1)
    axes[3].plot(t,d['BldPitch1'],lw=1)
    axes[4].plot(t,np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),lw=1)
for ax,label in zip(axes,['wind speed [m/s]','direction [deg]','NacYaw [deg]','pitch [deg]','tower resultant [kN m]']):ax.set_ylabel(label);ax.grid(alpha=.2)
axes[0].legend(ncol=5,fontsize=7);axes[-1].set_xlabel('simulation time [s]')
fig.suptitle('Case I near | Data: Nguyen (2012) analytic field; OpenFAST 5.0.0 + modified ROSCO 2.10.6; no turbulence')
fig.tight_layout();fig.savefig(PLOTS[0],dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4));b=lookup['instant']['metrics']['event']['tower_resultant_max_kNm']
for names,lab in [([f'stop_perfect_{t}' for t in (5,10,20,40)],'perfect'),(['stop_real_1D'],'real 1D')]:
    subset=[lookup[g] for g in names if g in lookup]
    if subset:ax.plot([x['actual_lead_s'] for x in subset],[100*(1-x['metrics']['event']['tower_resultant_max_kNm']/b) for x in subset],'o-' if len(subset)>1 else 'o',label=lab)
ax.axhline(0,color='gray',lw=.8);ax.set(xlabel='actual lead vs rotor 25 m/s [s]',ylabel='event tower resultant peak reduction vs instant [%]');ax.grid(alpha=.3);ax.legend()
fig.suptitle('Data: Nguyen (2012) field; NREL 5MW OpenFAST 5.0.0 + modified ROSCO 2.10.6; deterministic')
fig.tight_layout();fig.savefig(PLOTS[1],dpi=150);plt.close(fig)
DEST.write_text(json.dumps(dict(scope='amended A2 Guo-inspired; Case I only because Case III yaw gate failed',completed=len(runs),expected=len(manifest),
  solver_wall_s_previous_A2=1747.025,solver_wall_s_new=sum(r['wall_s'] for r in ledger),windows='full t>=60 until end; event from first 13m/s rotor crossing to 60s after last 25m/s',
  benefit_ratio_rule='(baseline-real)/(baseline-perfect), null when perfect benefit <=1% absolute baseline or nonpositive',runs=runs,benefit_ratios=ratios),indent=2)+'\n')
print('analyzed',len(runs),'of',len(manifest),DEST)
