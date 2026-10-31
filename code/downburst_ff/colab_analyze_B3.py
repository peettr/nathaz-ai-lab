"""Summarize paired Colab NTM gates and render compact diagnostic plots."""
from pathlib import Path
import json,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/content/a3_b3_1015')
def rows(file):return [json.loads(x) for x in (P/file).read_text().splitlines() if x.strip()]
scan=rows('timing_metrics.jsonl');ref=rows('reference_metrics_v2.jsonl');old=rows('gate_metrics_B2_complete.jsonl')
assert len(scan)==8 and len(ref)==6,(len(scan),len(ref))
assert all(z['rc']==0 for z in scan+ref)
fb=next(z['RotSpeed_std'] for z in old if z['seed']==112 and z['group']=='FB')
ss=sorted((z for z in scan if z['gain']==1),key=lambda z:z['delta_s']);xx=[z['delta_s'] for z in ss];yy=[z['RotSpeed_std_rpm'] for z in ss]
fig,ax=plt.subplots(figsize=(8,4.5));ax.plot(xx,yy,'o-',label='Own ROSCO 2.10.6 FF, gain 1');ax.axhline(fb,color='k',ls='--',label=f'Own FB seed 112: {fb:.4f} rpm');z=next(z for z in scan if z['gain']==.5);ax.scatter([0],[z['RotSpeed_std_rpm']],marker='s',s=65,label='Own FF gain 0.5 at Δ=0');ax.set(xlabel='Preview shift Δ (s; positive = earlier preview)',ylabel='Rotor speed std, 100–600 s (rpm)',title='NREL 5 MW, TurbSim IEC NTM A 16 m/s, seed 112');ax.grid(alpha=.3);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(P/'timing_scan_B3.png',dpi=180);plt.close(fig)
seeds=[112,203,317];x=np.arange(3);fig,ax=plt.subplots(figsize=(8,4.5));wv=.32
for i,g in enumerate(('FB','FF')):
 vals=[next(z['RotSpeed_std_rpm'] for z in ref if z['seed']==s and z['group']==g) for s in seeds]
 ax.bar(x+(i-.5)*wv,vals,width=wv,label=f'Task52 {g}')
 for k,v in enumerate(vals):ax.text(x[k]+(i-.5)*wv,v+0.003,f'{v:.3f}',ha='center',fontsize=8)
ax.set_xticks(x,seeds);ax.set(xlabel='TurbSim seed',ylabel='Rotor speed std, 100–600 s (rpm)',title='Task52 LDP→FFP→ROSCO 2.6, InflowWind lidar, NREL 5 MW');ax.grid(axis='y',alpha=.3);ax.legend();fig.tight_layout();fig.savefig(P/'reference_gate_B3.png',dpi=180);plt.close(fig)
ratios={str(s):next(z['RotSpeed_std_rpm'] for z in ref if z['seed']==s and z['group']=='FF')/next(z['RotSpeed_std_rpm'] for z in ref if z['seed']==s and z['group']=='FB') for s in seeds}
result={'own_scan':scan,'own_baseline_seed112_rpm':fb,'own_best_delta':min(ss,key=lambda z:z['RotSpeed_std_rpm'])['delta_s'],'own_best_improvement_pct':100*(1-min(yy)/fb),'reference':ref,'reference_ff_fb_ratios':ratios,'time_alignment':json.loads((P/'bts_time_alignment.json').read_text()),'status':'diagnostic; reference gate needs all 3 lower to pass'}
(P/'diagnostics_B3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('SUMMARY',json.dumps({'scan_n':len(scan),'ref_n':len(ref),'own_best_delta':result['own_best_delta'],'own_best_improvement_pct':result['own_best_improvement_pct'],'reference_ratios':ratios},ensure_ascii=False),flush=True)
