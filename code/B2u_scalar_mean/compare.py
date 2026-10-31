from pathlib import Path
import json,csv,statistics,math,hashlib
R=Path(__file__).resolve().parent
B=Path('./24_Urban_Wind_LBM/06_Logs/wp1b_ibm/inflow_ti/B2_offset_samples.json')
D=Path('./16_PETW/05_Literature_Wiki/99_Scratch/luw_caseE_20261017/Wang2025_Fig5_digitized.csv')
a=json.loads((R/'offset_samples_a_r10.json').read_text());b=json.loads(B.read_text());assert len(a['rows'])==len(b['rows'])==80
base={q['id']:q for q in b['rows']};out=[]
for q in a['rows']:
 id=q['id'];obs=q['after'];s=q['sample']['plus_dx'];old=base[id]['sample']['plus_dx'];S=s['sim_ratio'];Su=s['Su_ratio'];Sr=s['Srms_ratio'];Sstar=s['exp_ratio']
 assert math.isfinite(Su) and S-2e-5<=Su<=Sr+2e-5,(id,S,Su,Sr)
 out.append(dict(id=id,obs=obs,S=S,Su=Su,Sstar=Sstar,Srms=Sr,k=s['tke_m2s2'],solid_corners=8-s['fluid_corners'],Su_minus_Sstar=Su-Sstar,baseline_S=old['sim_ratio'],baseline_Sstar=old['exp_ratio']))
assert {q['id'] for q in out}==set(range(1,81))
def stats(rows,key):
 si=[q[key] for q in rows];ob=[q['obs'] for q in rows]
 return dict(mae=statistics.mean(abs(x-y) for x,y in zip(si,ob)),r=statistics.correlation(si,ob),mean_ratio=statistics.mean(si)/statistics.mean(ob),mean_pointwise_ratio=statistics.mean(x/y for x,y in zip(si,ob)))
metrics={'count':len(out),'all':{key:stats(out,key) for key in ('S','Su','Sstar','Srms')},'groups':{'Su_fast':[r['id'] for r in out if r['Su']/r['obs']>1.2],'Su_slow':[r['id'] for r in out if r['Su']/r['obs']<.8]},'special':{str(q['id']):q for q in out if q['id'] in (50,74)}}
with D.open() as f:les={int(q['id']):q for q in csv.DictReader(f)}
assert len(les)==80 and set(les)==set(range(1,81))
metrics['Wang_Fig5']={'digitized_WTE_vs_our_obs_mae':statistics.mean(abs(float(les[q['id']]['WTE'])-q['obs']) for q in out),'digitized_LES_vs_our_obs_mae':statistics.mean(abs(float(les[q['id']]['LES'])-q['obs']) for q in out),'digitized_LES_vs_digitized_WTE_mae':statistics.mean(abs(float(les[q['id']]['LES'])-float(les[q['id']]['WTE'])) for q in out),'B2u_Su_vs_our_obs_mae':metrics['all']['Su']['mae']}
(R/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
with (R/'points_80.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
print(json.dumps(metrics,indent=2))
