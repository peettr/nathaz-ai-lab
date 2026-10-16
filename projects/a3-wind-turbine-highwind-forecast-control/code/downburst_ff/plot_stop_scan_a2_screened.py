#!/usr/bin/env python3
"""Case I screened stop scan relative to instant threshold."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
h=Path(__file__).resolve().parent;out=h/'stop_scan_A2_I_near_screened.png'
if out.exists():raise RuntimeError('refuse overwrite')
j=json.loads((h/'metrics_A2_screened.json').read_text())
d={r['group']:r for r in j['runs'] if r['case']=='I_near'}
fig,ax=plt.subplots(figsize=(7,4));b=d['instant']['metrics']['event']['tower_resultant_max_kNm']
for quality,groups in [('perfect',[f'stop_perfect_{t}' for t in (5,10,20,40)]),('realistic 1D',['stop_real_1D'])]:
 x=[d[g]['actual_lead_s'] for g in groups];y=[100*(1-d[g]['metrics']['event']['tower_resultant_max_kNm']/b) for g in groups]
 ax.plot(x,y,'o-' if len(x)>1 else 'o',label=quality)
ax.axhline(0,color='gray',lw=.8);ax.set(xlabel='actual lead vs rotor 25 m/s [s]',ylabel='event tower resultant reduction vs instant [%]',title='Case I, no turbulence');ax.grid(alpha=.3);ax.legend()
fig.text(.02,.01,'Data: Nguyen (2012) analytic field; OpenFAST 5.0.0 NREL5MW + patched ROSCO 2.10.6. Case III screened out.',fontsize=8)
fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out,dpi=160);print(out)
