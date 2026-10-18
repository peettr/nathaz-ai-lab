#!/usr/bin/env python3
"""Aggregate segment A OpenFAST ASCII outputs into immutable metrics and figures."""
import json, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff/segment_a_v9')
M=HERE/'metrics_A.json'
FIGS=[HERE/f'timeseries_A_{c}.png' for c in ('I_near','III_offset')]+[HERE/'stop_scan_A.png']
if M.exists() or any(p.exists() for p in FIGS):raise RuntimeError('refuse overwrite result')
manifest=json.loads((ROOT/'manifest.json').read_text())
ledger=[json.loads(x) for x in (ROOT/'ledger.jsonl').read_text().splitlines()]
if len(ledger)!=28 or len(manifest)!=28 or any(x['returncode']!=0 for x in ledger):
    raise RuntimeError(f'incomplete/failed runs: {len(ledger)}/28')
by_key={(x['case'],x['group']):x for x in ledger}
if len(by_key)!=28:raise RuntimeError('duplicate run')
def extract(row):
    p=Path(row['runroot'])/'NREL-5MW.out'
    with p.open() as f:
        for i,line in enumerate(f):
            if i==6:labels=line.split();break
    wanted=['Time','Wind1VelX','Wind1VelY','BldPitch1','RotSpeed','RootMyb1','YawBrMzp','TwrBsMxt','TwrBsMyt','NacYaw']
    idx=[labels.index(x) for x in wanted]
    data=np.loadtxt(p,skiprows=8,usecols=idx)
    if data.shape[0]<100 or not np.all(np.isfinite(data)):raise RuntimeError(f'bad output: {p}')
    if abs(data[-1,0]-(row['end']-row['start']))>.1:raise RuntimeError(f'incomplete simulation: {p}')
    a=dict(zip(wanted,data.T))
    a['TwrBsResultant']=np.hypot(a['TwrBsMxt'],a['TwrBsMyt'])
    return a
all_data={};out=[]
for row in manifest:
    a=extract(by_key[(row['case'],row['group'])]);all_data[(row['case'],row['group'])]=a
    mask=a['Time']>=60
    if not np.any(mask):raise RuntimeError('no event window')
    val=lambda key:a[key][mask]
    metric={
       'tower_resultant_max_kNm':float(np.max(val('TwrBsResultant'))),
       'tower_fore_aft_absmax_kNm':float(np.max(np.abs(val('TwrBsMyt')))),
       'tower_fore_aft_positive_max_kNm':float(np.max(val('TwrBsMyt'))),
       'tower_fore_aft_negative_min_kNm':float(np.min(val('TwrBsMyt'))),
       'tower_side_side_absmax_kNm':float(np.max(np.abs(val('TwrBsMxt')))),
       'tower_top_yaw_absmax_kNm':float(np.max(np.abs(val('YawBrMzp')))),
       'root_flapwise_b1_positive_max_kNm':float(np.max(val('RootMyb1'))),
       'root_flapwise_b1_negative_min_kNm':float(np.min(val('RootMyb1'))),
       'rotor_speed_peak_rpm':float(np.max(val('RotSpeed'))),
       'rotor_speed_overshoot_vs_12p1_rpm_pct':float((np.max(val('RotSpeed'))/12.1-1)*100),
       'pitch_max_deg':float(np.max(val('BldPitch1'))),
       'pitch_rate_max_abs_deg_s':float(np.max(np.abs(np.diff(a['BldPitch1'])/np.diff(a['Time'])))),
       'yaw_rate_max_abs_deg_s':float(np.max(np.abs(np.diff(a['NacYaw'])/np.diff(a['Time'])))),
       'max_abs_wind_dir_deg':float(np.max(np.abs(np.degrees(np.arctan2(val('Wind1VelY'),val('Wind1VelX')))))),
       'sample_count':int(np.sum(mask))}
    out.append(dict(case=row['case'],group=row['group'],stop_T_requested_s=row['stop_T'],
       trigger_abs_s=row['trigger_abs'],actual_lead_vs_cross_s=float(row['crossing_abs']-row['trigger_abs']),
       scheduled_shutdown_s=float(row['trigger_abs']-row['start']),gain=row['gain'],
       elapsed_s=by_key[(row['case'],row['group'])]['elapsed_s'],metrics=metric))
result={'scope':'deterministic only, 2 storm paths; no turbulence/seeds or 10% B threshold',
 'data_source':'Nguyen (2012) Eq 3.2-3.11, 3.21-3.24 Table 4.4; OpenFAST 5.0.0 NREL5MW onshore; ROSCO 2.10.6 local patch; WSL segment_a_v9',
 'event_window':'simulated time 60 s to end of run; wind onset 13 m/s occurs at ~60 s; end is 60 s after last above-25 m/s sampled value',
 'runs':out,'successful_runs':len(out),'total_solver_wall_s':sum(r['elapsed_s'] for r in out),
 'case_provenance':{c:json.loads((ROOT/c/'provenance.json').read_text()) for c in ('I_near','III_offset')}}
for c in ('I_near','III_offset'):
    fig,axes=plt.subplots(4,1,figsize=(11,10),sharex=True)
    for group in ['feedback','perfect','real_1D','real_2D']:
        a=all_data[(c,group)];t=a['Time']; lab=group
        axes[0].plot(t,np.hypot(a['Wind1VelX'],a['Wind1VelY']),label=lab,lw=1)
        axes[1].plot(t,np.degrees(np.arctan2(a['Wind1VelY'],a['Wind1VelX'])),label=lab,lw=1)
        axes[2].plot(t,a['BldPitch1'],label=lab,lw=1)
        axes[3].plot(t,a['TwrBsResultant'],label=lab,lw=1)
    axes[0].set_ylabel('hub wind [m/s]');axes[1].set_ylabel('wind direction [deg]')
    axes[2].set_ylabel('blade 1 pitch [deg]');axes[3].set_ylabel('tower-base resultant [kN m]')
    axes[3].set_xlabel('time since local simulation start [s]');axes[0].legend(ncol=4,fontsize=8)
    for a in axes:a.axvline(60,color='gray',ls=':',lw=.7)
    fig.suptitle(f'{c}: Nguyen 2012 deterministic 4D field projected to rotor-uniform wind; OpenFAST 5.0.0 + ROSCO 2.10.6\nData: Nguyen 2012 Eqs. 3.2–3.11, 3.21–3.24 Table 4.4; model NREL 5MW; no turbulence, exploratory')
    fig.tight_layout();fig.savefig(HERE/f'timeseries_A_{c}.png',dpi=145);plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(12,4.5))
for a,c in zip(ax,('I_near','III_offset')):
    base=next(x for x in out if x['case']==c and x['group']=='stop_perfect_0')['metrics']['tower_resultant_max_kNm']
    for quality in ('perfect','real_1D'):
        rr=[x for x in out if x['case']==c and x['group'].startswith('stop_'+quality+'_')]
        rr.sort(key=lambda x:x['stop_T_requested_s'])
        a.plot([x['stop_T_requested_s'] for x in rr],[(1-x['metrics']['tower_resultant_max_kNm']/base)*100 for x in rr],marker='o',label=quality)
        for x in rr:
            if quality=='real_1D' and x['stop_T_requested_s']>0:
                a.annotate(f"actual {x['actual_lead_vs_cross_s']:.1f}s",(x['stop_T_requested_s'],(1-x['metrics']['tower_resultant_max_kNm']/base)*100),xytext=(2,5),textcoords='offset points',fontsize=7)
    a.set(xlabel='requested lead T [s]; T=0 means +50 s protection',ylabel='tower resultant reduction vs T=0 [%]',title=c)
    a.legend();a.grid(alpha=.3)
fig.suptitle('Data: Nguyen 2012 analytic wind + OpenFAST 5.0.0 NREL5MW + ROSCO 2.10.6 patch; deterministic only.\nRealistic triggers cannot precede upstream detection; actual lead annotated.')
fig.tight_layout();fig.savefig(HERE/'stop_scan_A.png',dpi=145);plt.close(fig)
M.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('created',M,*FIGS,sep='\n')
for c in ('I_near','III_offset'):
    for g in ('feedback','perfect','real_1D','real_2D','stop_perfect_0','stop_perfect_40','stop_real_1D_40'):
        x=next(x for x in out if (x['case'],x['group'])==(c,g))
        print(c,g,'tower',round(x['metrics']['tower_resultant_max_kNm'],2),'trigger',round(x['trigger_abs_s'],2),'actual_lead',round(x['actual_lead_vs_cross_s'],2))
