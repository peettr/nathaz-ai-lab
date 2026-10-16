#!/usr/bin/env python3
"""Analyze only finished A2 simulations; write new A2 artifacts without overwrites."""
import json, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff/segment_a2_v1')
DEST=HERE/'metrics_A2.json'
PLOTS=[HERE/f'timeseries_A2_{c}.png' for c in ('I_near','III_offset')]+[HERE/'stop_scan_A2.png']
if DEST.exists() or any(p.exists() for p in PLOTS):raise RuntimeError('refuse to overwrite A2 artifact')
manifest=json.loads((ROOT/'manifest.json').read_text())
ledger=[json.loads(s) for s in (ROOT/'ledger.jsonl').read_text().splitlines()]
if len(ledger)!=len({(r['case'],r['group']) for r in ledger}):raise RuntimeError('duplicate run')
by={}; rows=[]
fields=['Time','Wind1VelX','Wind1VelY','BldPitch1','RotSpeed','RootMyb1','YawBrMzp','TwrBsMxt','TwrBsMyt','NacYaw']
for r in ledger:
    if r['returncode']!=0:continue
    f=Path(r['runroot'])/'NREL-5MW.out'
    with f.open() as fh:
        for i,line in enumerate(fh):
            if i==6:cols=line.split();break
    a=np.loadtxt(f,skiprows=8,usecols=[cols.index(x) for x in fields]);d=dict(zip(fields,a.T));
    if abs(d['Time'][-1]-(r['end']-r['start']))>.1:raise RuntimeError(f'incomplete {f}')
    by[(r['case'],r['group'])]=d
    p=json.loads((ROOT/r['case']/'provenance.json').read_text())
    masks={'full':d['Time']>=60,'event':(d['Time']>=p['onset_13_abs']-r['start'])&(d['Time']<=p['last_25_abs']-r['start']+60)}
    scopes={}
    for label,mask in masks.items():
        v=lambda key:d[key][mask]
        tw=np.hypot(v('TwrBsMxt'),v('TwrBsMyt'));rpm=v('RotSpeed')
        scopes[label]=dict(tower_resultant_max_kNm=float(tw.max()),tower_fore_aft_absmax_kNm=float(np.abs(v('TwrBsMyt')).max()),
            tower_fore_aft_positive_max_kNm=float(v('TwrBsMyt').max()),tower_fore_aft_negative_min_kNm=float(v('TwrBsMyt').min()),
            tower_side_side_absmax_kNm=float(np.abs(v('TwrBsMxt')).max()),tower_top_yaw_absmax_kNm=float(np.abs(v('YawBrMzp')).max()),
            blade1_root_flapwise_positive_max_kNm=float(v('RootMyb1').max()),blade1_root_flapwise_negative_min_kNm=float(v('RootMyb1').min()),
            rotor_speed_peak_rpm=float(rpm.max()),rotor_speed_overshoot_vs_12p1_pct=float((rpm.max()/12.1-1)*100),
            blade_pitch_peak_deg=float(v('BldPitch1').max()),nac_yaw_range_deg=[float(v('NacYaw').min()),float(v('NacYaw').max())])
    t=d['Time'];yaw=d['NacYaw'];dt=int(round(1/np.median(np.diff(t))))
    rows.append(dict(case=r['case'],group=r['group'],actual_lead_s=r['actual_lead_s'],wall_s=r['wall_s'],
                     runroot=r['runroot'],yaw_max_1s_change_deg=float(np.abs(yaw[dt:]-yaw[:-dt]).max()),metrics=scopes))
lookup={(r['case'],r['group']):r for r in rows}
keys=['tower_resultant_max_kNm','tower_fore_aft_absmax_kNm','tower_fore_aft_positive_max_kNm',
      'tower_fore_aft_negative_min_kNm','tower_side_side_absmax_kNm','tower_top_yaw_absmax_kNm',
      'blade1_root_flapwise_positive_max_kNm','blade1_root_flapwise_negative_min_kNm','rotor_speed_overshoot_vs_12p1_pct']
# Negative-direction magnitude and overspeed performance oriented as larger = worse.
def magnitude(key,value):return -value if key.endswith('negative_min_kNm') else value
ratio=[]
for case in ('I_near','III_offset'):
    for scope in ('full','event'):
        for base,perfect,real,kind in [('feedback','perfect','real_1D','pitch_1D'),('feedback','perfect','real_2D','pitch_2D')]+[
                ('instant',f'stop_perfect_{T}','stop_real_1D',f'stop_T{T}_real_1D') for T in (5,10,20,40)]:
            for key in keys:
                trip=[lookup.get((case,g)) for g in (base,perfect,real)]
                if any(x is None for x in trip):ratio.append(dict(case=case,window=scope,kind=kind,metric=key,ratio=None,status='missing'));continue
                b,p,q=[magnitude(key,x['metrics'][scope][key]) for x in trip]
                benefit=b-p
                if benefit<=.01*abs(b) or benefit<=0:val=None;status='not_applicable_under_1pct'
                else:val=(b-q)/benefit;status='valid'
                ratio.append(dict(case=case,window=scope,kind=kind,metric=key,ratio=val,status=status,
                                  baseline=b,perfect=p,real=q))
for case in ('I_near','III_offset'):
    fig,axes=plt.subplots(5,1,figsize=(10,11),sharex=True)
    for group in ('feedback','instant','perfect','real_1D','real_2D'):
        d=by.get((case,group))
        if not d:continue
        t=d['Time'];axes[0].plot(t,np.hypot(d['Wind1VelX'],d['Wind1VelY']),label=group,lw=1)
        axes[1].plot(t,np.degrees(np.arctan2(d['Wind1VelY'],d['Wind1VelX'])),lw=1)
        axes[2].plot(t,d['NacYaw'],lw=1)
        axes[3].plot(t,d['BldPitch1'],lw=1)
        axes[4].plot(t,np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),lw=1)
    for ax,name in zip(axes,['wind speed [m/s]','direction [deg]','NacYaw [deg]','pitch [deg]','tower resultant [kN m]']):ax.set_ylabel(name);ax.grid(alpha=.2)
    axes[0].legend(ncol=5,fontsize=7);axes[4].set_xlabel('simulation time [s]')
    fig.suptitle(f'{case} | Data: Nguyen (2012) analytic 4D field, NREL 5MW OpenFAST 5.0.0 + ROSCO 2.10.6 patch; deterministic, no turbulence')
    fig.tight_layout();fig.savefig(HERE/f'timeseries_A2_{case}.png',dpi=150);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=True)
for ax,case in zip(axes,('I_near','III_offset')):
    baseline=lookup.get((case,'instant'))
    if baseline:
        b=baseline['metrics']['event']['tower_resultant_max_kNm']
        for quality in ('perfect','real_1D'):
            names=[f'stop_perfect_{T}' for T in (5,10,20,40)] if quality=='perfect' else ['stop_real_1D']
            xs=[];ys=[]
            for g in names:
                x=lookup.get((case,g))
                if x:xs.append(x['actual_lead_s']);ys.append(100*(1-x['metrics']['event']['tower_resultant_max_kNm']/b))
            if xs:ax.plot(xs,ys,'o-' if len(xs)>1 else 'o',label=quality)
    ax.axvline(0,color='gray',lw=.8);ax.set(title=case,xlabel='actual lead vs rotor 25 m/s [s]',ylabel='event tower peak reduction vs instant [%]');ax.grid(alpha=.3);ax.legend(fontsize=8)
fig.suptitle('Data: Nguyen (2012) field + OpenFAST 5.0.0 / patched ROSCO 2.10.6; deterministic no turbulence')
fig.tight_layout();fig.savefig(HERE/'stop_scan_A2.png',dpi=150);plt.close(fig)
DEST.write_text(json.dumps(dict(scope='A2 deterministic partial or complete; old v9/v10 files untouched',completed=len(rows),expected=len(manifest),
    missing=[dict(case=x['case'],group=x['group']) for x in manifest if (x['case'],x['group']) not in lookup],
    solver_wall_s=sum(x['wall_s'] for x in ledger),
    windows='full t>=60 until end; event from first 13m/s rotor crossing to 60s past final 25m/s crossing',
    benefit_ratio_rule='(baseline-real)/(baseline-perfect); null when perfect improvement <=1% absolute baseline or nonpositive',runs=rows,benefit_ratios=ratio),indent=2)+'\n')
print('A2 analyzed',len(rows),'/',len(manifest),'wall s',sum(x['wall_s'] for x in ledger))
