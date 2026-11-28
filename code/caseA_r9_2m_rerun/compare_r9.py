from pathlib import Path
import json,math,statistics
r=Path(__file__).parent
new=json.loads((r/'samples_caseA_r9_2m.json').read_text());old=json.loads((r/'metrics_caseA_turb.json').read_text())
def metric(rows,shift):
 a=[v[shift]['speed_UH'] for v in rows];b=[v['obs_speed'] for v in rows];ak=[v[shift]['k_UH2'] for v in rows];bk=[v['obs_k'] for v in rows];keep=[i for i,v in enumerate(bk) if abs(v)>.05]
 def corr(x,y):
  xm=statistics.mean(x);ym=statistics.mean(y);den=math.sqrt(sum((v-xm)**2 for v in x)*sum((v-ym)**2 for v in y));return sum((v-xm)*(w-ym) for v,w in zip(x,y))/den if den else None
 def fac(x,y):return sum(.5*w<=v<=2*w for v,w in zip(x,y))/len(x)
 rmse=math.sqrt(statistics.mean((v-w)**2 for v,w in zip(a,b)));ka=[ak[i] for i in keep];kb=[bk[i] for i in keep]
 return dict(n=len(a),n_tke=len(keep),FAC2=fac(a,b),q_abs025=sum(abs(v-w)<=.25 for v,w in zip(a,b))/len(a),q_rel025=sum(abs(v-w)<=.25*abs(w) for v,w in zip(a,b))/len(a),r=corr(a,b),NRMSE_range=rmse/(max(b)-min(b)),NRMSE_mean=rmse/statistics.mean(b),TKE_FAC2=fac(ka,kb),TKE_r=corr(ka,kb),mean_ratio=statistics.mean(a)/statistics.mean(b),mixed_solid=sum(v[shift]['fluid_corners']<8 for v in rows))
out={'main':{},'diagnostic':{},'old_delta':{},'mask':new['mask']}
for g,rows in new['groups'].items():
 out['main'][g]={s:metric(rows,s) for s in ('no_shift','plus_xy','plus_xyz')};oldg={'z4_actual':'z8','z40_actual':'z80','vertical_actual':'vertical'}[g];ref=old['turb'][oldg];out['old_delta'][g]={k:out['main'][g]['plus_xyz'][k]-ref[k] for k in ('FAC2','q_abs025','q_rel025','r','NRMSE_range','NRMSE_mean','TKE_FAC2','TKE_r','mean_ratio','n','n_tke') if k in ref}
for g,rows in new['diagnostic'].items():out['diagnostic'][g]={s:metric(rows,s) for s in ('no_shift','plus_xy','plus_xyz')}
(r/'metrics_caseA_r9_2m.json').write_text(json.dumps(out,indent=2));print('METRICS_DONE',json.dumps(out['old_delta']))
