"""Postprocess r10 variants and r7 with a common 80-point denominator."""
from pathlib import Path
import csv,json,statistics,math,ast
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).parent;B=R.parent
r7=json.loads((B/'offset_samples_r7.json').read_text());order=ast.literal_eval((B/'digitize_han_fig1d.py').read_text().split('order=')[1].split('\npaper=')[0]);paper=ast.literal_eval((B/'digitize_han_fig1d.py').read_text().split('paper=')[1].split('\nassert')[0]);P=dict(zip(order,paper));groups=[(0,23,'wake/near'),(24,33,'wake/far'),(34,44,'nonwake/far'),(45,79,'nonwake/near')]
def met(rows,obs,shift,key,ids=None):
 rows=[p for p in rows if ids is None or p['id'] in ids]; x=[p[obs] for p in rows];y=[p['sample'][shift][key] for p in rows]; n=len(x)
 return dict(n=n,mae=statistics.mean(abs(a-b) for a,b in zip(x,y)),r=statistics.correlation(x,y) if n>1 and len(set(x))>1 and len(set(y))>1 else None,ratio=statistics.mean(y)/statistics.mean(x),sim_mean=statistics.mean(y),obs_mean=statistics.mean(x),mixed=sum(p['sample'][shift]['fluid_corners']<8 for p in rows))
def bestfit(data):
 fit=data['mask_fit']; out={}
 for z in sorted(set(p['z_vtk'] for p in fit)):
  ranked=sorted((p for p in fit if p['z_vtk']==z),key=lambda p:p['iou'] or -1,reverse=True)
  out[str(z)]=ranked[:3]
 return out
allruns={'r7':r7}
for v in 'abcd':
 p=R/f'offset_samples_{v}_r10.json'
 if p.exists():allruns['R10'+v]=json.loads(p.read_text())
res={'source':'r7 and r10 same west geometry and xls W after/before, 15.9m reference','groups':groups,'runs':{}}
for name,data in allruns.items():
 rows=data['rows'];assert len(rows)==80 and {p['id'] for p in rows}==set(order)
 o={'mask_best':bestfit(data),'upstream':data['upstream'],'metrics':{},'group_mae':{}}
 for shift in ['plus_dx','no_offset']:
  o['metrics'][shift]={};o['group_mae'][shift]={}
  for obs in ['after','before']:
   o['metrics'][shift][obs]={}
   for key in ['sim_ratio','exp_ratio']:o['metrics'][shift][obs][key]=met(rows,obs,shift,key)
   if obs=='after':
    o['group_mae'][shift]={label:{key:met(rows,obs,shift,key,set(order[a:b+1]))['mae'] for key in ['sim_ratio','exp_ratio']} for a,b,label in groups}
 # Fixed subset from r7 tail/remote-building group of 10, plus run-specific slow set for context
 low7={p['id'] for p in r7['rows'] if p['sample']['plus_dx']['sim_ratio']<.10}
 o['low_r7_ids']=sorted(low7);o['low_r7']={key:met(rows,'after','plus_dx',key,low7) for key in ['sim_ratio','exp_ratio']}
 res['runs'][name]=o
(R/'metrics_r10.json').write_text(json.dumps(res,indent=2,ensure_ascii=False))
with (R/'summary_r10.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['run','offset','state','quantity','mae','r','sim_obs_mean_ratio','mixed_stencils'])
 for name,d in res['runs'].items():
  for offset,states in d['metrics'].items():
   for state,qs in states.items():
    for q,m in qs.items():w.writerow([name,offset,state,q,m['mae'],m['r'],m['ratio'],m['mixed']])
fig,axs=plt.subplots(2,1,figsize=(17,9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
wt=[next(p['after'] for p in r7['rows'] if p['id']==i) for i in order];x=range(80);ax=axs[0];ax.plot(x,wt,'-s',color='#222222',ms=4,label='Wind tunnel After W')
ax.plot(x,paper,'-o',ms=4,color='#df7146',label='Han Fig 1(d) digitized ±0.05')
colors={'r7':'#2b75c5','R10a':'#15a575','R10b':'#b357ac','R10c':'#ceaa23','R10d':'#1a7986'}
for name,data in allruns.items():
 ours=[next(p['sample']['plus_dx']['exp_ratio'] for p in data['rows'] if p['id']==i) for i in order]
 ax.plot(x,ours,'-',color=colors[name],lw=1.25,label=f'{name} scalar MAE {res["runs"][name]["metrics"]["plus_dx"]["after"]["exp_ratio"]["mae"]:.3f}')
 axs[1].plot(x,[a-b for a,b in zip(ours,wt)],'-',lw=1.2,color=colors[name],label=name)
for a,b,label in groups:
 for q in axs:q.axvspan(a-.5,b+.5,color='#eeeeee' if a in (0,34) else 'white',zorder=-1)
 ax.text((a+b)/2,1.52,label,ha='center',fontsize=10)
ax.set(ylabel='U / Uref (15.9m)',ylim=(0,1.6),title='Case E W: WT / Han Fig 1(d) / LUW scalar approximation');ax.legend(ncol=4,fontsize=8)
axs[1].axhline(0,c='k',lw=.7);axs[1].set(ylabel='LUW - WT',xlabel='point ID (Han Fig 1(d) order)');axs[1].set_xticks(list(x));axs[1].set_xticklabels(order,rotation=90,fontsize=7)
fig.tight_layout();fig.savefig(R/'CaseE_W_paper_WT_r10a.png',dpi=145)
print('runs',list(allruns),'main',[(n,round(d['metrics']['plus_dx']['after']['exp_ratio']['mae'],4)) for n,d in res['runs'].items()])
