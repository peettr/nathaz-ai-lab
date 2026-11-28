#!/usr/bin/env python3
"""Partial corrected protection-enabled analysis; never overwrites v9 exploratory files."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff/segment_a_v10')
DEST=HERE/'metrics_A_v10_partial.json'
FIGS=[HERE/f'timeseries_A_v10_{c}.png' for c in ('I_near','III_offset')]+[HERE/'stop_scan_A_v10.png']
if DEST.exists() or any(f.exists() for f in FIGS):raise RuntimeError('refuse overwrite')
manifest={(r['case'],r['group']):r for r in json.loads((ROOT/'manifest.json').read_text())}
ledger=[json.loads(l) for l in (ROOT/'ledger.jsonl').read_text().splitlines()]
extra=Path('./lab_a3/downburst_ff/segment_a_v11/ledger.jsonl')
ledger += [json.loads(l) for l in extra.read_text().splitlines()]
if len(ledger)!=len({(r['case'],r['group']) for r in ledger}) or any(r['returncode']!=0 for r in ledger):raise RuntimeError('duplicate/failed')
by={};metrics=[]
for r in ledger:
    key=(r['case'],r['group']);q=Path(r['runroot'])/'NREL-5MW.out'
    with q.open() as f:
        for i,line in enumerate(f):
            if i==6:cols=line.split();break
    fields=['Time','Wind1VelX','Wind1VelY','BldPitch1','RotSpeed','RootMyb1','YawBrMzp','TwrBsMxt','TwrBsMyt','NacYaw']
    a=np.loadtxt(q,skiprows=8,usecols=[cols.index(x) for x in fields]);d=dict(zip(fields,a.T));by[key]=d
    m=d['Time']>=60
    if not np.any(m) or abs(d['Time'][-1]-(r['end']-r['start']))>.1:raise RuntimeError(f'incomplete {key}')
    v=lambda name:d[name][m]
    tower=np.hypot(v('TwrBsMxt'),v('TwrBsMyt'))
    metrics.append(dict(case=r['case'],group=r['group'],requested_T_s=r['stop_T'],
        actual_lead_s=r['crossing_abs']-r['trigger_abs'],trigger_abs_s=r['trigger_abs'],wall_s=r['elapsed_s'],
        metrics=dict(tower_resultant_max_kNm=float(np.max(tower)),tower_fore_aft_absmax_kNm=float(np.max(np.abs(v('TwrBsMyt')))),
            tower_fore_aft_positive_max_kNm=float(np.max(v('TwrBsMyt'))),tower_fore_aft_negative_min_kNm=float(np.min(v('TwrBsMyt'))),
            tower_side_side_absmax_kNm=float(np.max(np.abs(v('TwrBsMxt')))),tower_top_yaw_absmax_kNm=float(np.max(np.abs(v('YawBrMzp')))),
            blade1_root_flapwise_positive_max_kNm=float(np.max(v('RootMyb1'))),blade1_root_flapwise_negative_min_kNm=float(np.min(v('RootMyb1'))),
            rotor_speed_peak_rpm=float(np.max(v('RotSpeed'))),rotor_speed_overshoot_vs_12p1_pct=float((np.max(v('RotSpeed'))/12.1-1)*100),
            blade_pitch_peak_deg=float(np.max(v('BldPitch1'))),yaw_peak_abs_deg=float(np.max(np.abs(v('NacYaw')))),
            max_wind_direction_abs_deg=float(np.max(np.abs(np.rad2deg(np.arctan2(v('Wind1VelY'),v('Wind1VelX')))))))))
for case in ('I_near','III_offset'):
    fig,ax=plt.subplots(4,1,figsize=(10,10),sharex=True)
    for g in ('feedback','perfect','real_1D','real_2D'):
        if (case,g) not in by:continue
        d=by[(case,g)];t=d['Time'];ax[0].plot(t,np.hypot(d['Wind1VelX'],d['Wind1VelY']),label=g,lw=1)
        ax[1].plot(t,np.rad2deg(np.arctan2(d['Wind1VelY'],d['Wind1VelX'])),label=g,lw=1)
        ax[2].plot(t,d['BldPitch1'],label=g,lw=1)
        ax[3].plot(t,np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),label=g,lw=1)
    for a,l in zip(ax,('horizontal wind [m/s]','wind direction [deg]','pitch [deg]','tower resultant [kN m]')):
        a.set_ylabel(l);a.axvline(60,color='gray',ls=':',lw=.7)
    ax[0].legend(ncol=4,fontsize=8);ax[3].set_xlabel('simulation time [s]')
    fig.suptitle(f'{case}: corrected protection-enabled runs; only available groups shown\nData: Nguyen 2012 Eqs. 3.2–3.11, 3.21–3.24, Table 4.4; OpenFAST 5.0.0 NREL5MW + ROSCO 2.10.6 patch; no turbulence')
    fig.tight_layout();fig.savefig(HERE/f'timeseries_A_v10_{case}.png',dpi=140);plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(11,4),sharey=True)
for a,case in zip(ax,('I_near','III_offset')):
    base=next((x['metrics']['tower_resultant_max_kNm'] for x in metrics if (x['case'],x['group'])==(case,'stop_perfect_0')),None)
    if base is None:
        base=next((x['metrics']['tower_resultant_max_kNm'] for x in metrics if (x['case'],x['group'])==(case,'feedback')),None)
    for quality in ('perfect','real_1D'):
        rows=sorted([x for x in metrics if x['case']==case and x['group'].startswith('stop_'+quality+'_')],key=lambda x:x['requested_T_s'])
        if rows and base is not None:a.plot([x['requested_T_s'] for x in rows],[100*(1-x['metrics']['tower_resultant_max_kNm']/base) for x in rows],marker='o',label=quality)
    a.set(title=case,xlabel='requested T [s]; T=0 denotes +50s protection',ylabel='tower resultant reduction vs T=0 [%]');a.grid(alpha=.3);a.legend(fontsize=8)
fig.suptitle('Partial protection-enabled T scan; missing points not interpolated. Data: Nguyen 2012 + OpenFAST 5.0.0 + ROSCO 2.10.6 patch')
fig.tight_layout();fig.savefig(HERE/'stop_scan_A_v10.png',dpi=140);plt.close(fig)
DEST.write_text(json.dumps({'scope':'partial corrected SD_Mode=1; v9 results are invalid for mandated comparison','completed':len(metrics),
 'expected':28,'solver_wall_s':sum(r['elapsed_s'] for r in ledger),'missing':[{'case':c,'group':g} for c,g in manifest if (c,g) not in by],
 'window':'simulation t>=60 to end; end ~60s after last >25m/s','runs':metrics},indent=2)+'\n')
print('completed',len(metrics),'missing',28-len(metrics))
for r in metrics:
 print(r['case'],r['group'],round(r['metrics']['tower_resultant_max_kNm']),round(r['actual_lead_s'],1))
