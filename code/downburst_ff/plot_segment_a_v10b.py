#!/usr/bin/env python3
"""Plot corrected partial-A figures, gaps shown as gaps; no overwrite of earlier exploratory figures."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
ROOT=Path('./lab_a3/downburst_ff')
MET=json.loads((OUT/'metrics_A_v10_partial.json').read_text())['runs']
figpaths=[OUT/f'timeseries_A_v10c_{c}.png' for c in ('I_near','III_offset')]+[OUT/'stop_scan_A_v10c.png']
if any(p.exists() for p in figpaths):raise RuntimeError('refuse overwrite')
for case in ('I_near','III_offset'):
    fig,axs=plt.subplots(4,1,figsize=(11.5,10.5),sharex=True)
    for label in ('feedback','perfect','real_1D','real_2D'):
        rr=next((r for r in MET if (r['case'],r['group'])==(case,label)),None)
        if rr is None:continue
        root=ROOT/('segment_a_v11' if (case,label)==('I_near','real_1D') else 'segment_a_v10')/f'run_{case}_{label}'
        p=root/'NREL-5MW.out'
        with p.open() as f:
            for i,l in enumerate(f):
                if i==6:cols=l.split();break
        req=['Time','Wind1VelX','Wind1VelY','BldPitch1','TwrBsMxt','TwrBsMyt']
        z=np.loadtxt(p,skiprows=8,usecols=[cols.index(x) for x in req]);t,u,v,pit,mx,my=z.T
        for ax,val in zip(axs,(np.hypot(u,v),np.rad2deg(np.arctan2(v,u)),pit,np.hypot(mx,my))):
            ax.plot(t,val,label=label,lw=1.1)
    for ax,y in zip(axs,('horizontal speed (m/s)','direction (deg)','blade 1 pitch (deg)','tower-base resultant (kN m)')):
        ax.set_ylabel(y);ax.axvline(60,color='gray',lw=.8,ls=':',label='analysis starts at t=60 s' if ax is axs[0] else None);ax.grid(alpha=.2)
    axs[0].legend(fontsize=8,ncol=5);axs[-1].set_xlabel('simulation time (s)')
    fig.suptitle(f'{case}: shutdown enabled; deterministic downburst; common controller binary',y=.988,fontsize=12)
    fig.text(.01,.012,'Data: Nguyen (2012) sec. 3.3, Table 4.4; OpenFAST 5.0.0 NREL 5MW + local ROSCO 2.10.6 patch.\nNo turbulence; rotor-uniform WindType 2. Actual yaw did not track rotating wind; not a validated load estimate.',fontsize=8)
    fig.tight_layout(rect=[0,.065,1,.97]);fig.savefig(OUT/f'timeseries_A_v10c_{case}.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(11.5,5),sharey=True)
allx=[0,5,10,20,40]
for a,case in zip(ax,('I_near','III_offset')):
    base=next(r['metrics']['tower_resultant_max_kNm'] for r in MET if (r['case'],r['group'])==(case,'feedback'))
    for quality,marker in [('perfect','o'),('real_1D','s')]:
        y=[]
        for x in allx:
            r=next((r for r in MET if (r['case'],r['group'])==(case,f'stop_{quality}_{x}')),None)
            # Same feedback configuration at T=0, but distinguish not independently run.
            y.append(100*(1-r['metrics']['tower_resultant_max_kNm']/base) if r else np.nan)
        a.plot(allx,y,marker=marker,lw=1.3,label=quality)
        for x,v in zip(allx,y):
            if np.isnan(v):a.plot(x,0,marker='x',color='0.5',ms=7)
    a.set_xticks(allx);a.set(title=case,xlabel='requested lead T (s); T=0 means +50s shutdown',ylabel='tower-base resultant reduction (%)');a.grid(alpha=.25);a.legend(fontsize=8)
fig.suptitle('Partial A scan: grey x = not run; real 1D actual lead at most 4.6-4.7 s')
fig.text(.01,.012,'Data: Nguyen (2012) sec. 3.3 / Table 4.4; OpenFAST 5.0.0 NREL 5MW + local ROSCO 2.10.6 patch.\nNo turbulence; offset-path yaw tracking did not function.',fontsize=8)
fig.tight_layout(rect=[0,.08,1,.94]);fig.savefig(OUT/'stop_scan_A_v10c.png',dpi=150);plt.close(fig)
print('created',*[str(p) for p in figpaths])
