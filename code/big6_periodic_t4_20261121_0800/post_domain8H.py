#!/usr/bin/env python3.10
"""Postprocess verified 8H window JSON against frozen small-domain 30T windows."""
import csv,json,hashlib,math,pathlib,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).resolve().parent
O=R.parent/'longspin_20261120_002118_v3'
sessions=list(R.glob('session_*/evidence'))
assert len(sessions)==1,sessions
E=sessions[0]
assert (E/'run.done').is_file() and json.loads((E/'run.done').read_text())['windows']==11
windows=[]
for k in range(1,12):
 p=E/f'window_{k:02d}.json';h=hashlib.sha256(p.read_bytes()).hexdigest()
 assert h==(E/(p.name+'.sha256')).read_text().strip()
 w=json.loads(p.read_text());assert w['window']==k and len(w['U_profile_si_mps'])==64
 windows.append(w)
refE=O/'session_luw-t17-a100-df21176d/evidence'
ref=[]
for k in (10,11):
 p=refE/f'window_{k:02d}.json';assert hashlib.sha256(p.read_bytes()).hexdigest()==(refE/(p.name+'.sha256')).read_text().strip()
 ref.append(json.loads(p.read_text()))
fields=['V1_ratio','R_uu_x_half','R_uu_y_half','Px_begin','Px_end','Px_mean','k_res_z9p5','k_res_over_ustar_sq','e_2p5','S2b_rms']
with (R/'WINDOWS_DOMAIN8H.csv').open('x',newline='') as f:
 wr=csv.writer(f);wr.writerow(['window','start_T','end_T','start_step','end_step']+fields)
 for w in windows:wr.writerow([w['window'],2*(w['window']-1),2*w['window'],*w['step_range']]+[w[x] for x in fields])
with (R/'PROFILE_20_22T.csv').open('x',newline='') as f:
 wr=csv.writer(f);wr.writerow(['k','z_m','U_mps'])
 for k in range(1,21):wr.writerow([k,k-0.5,windows[-1]['U_profile_si_mps'][str(k)]])
last=windows[-1]
comparisons={}
for field in ('e_2p5','S2b_rms'):
 baseline=sum(w[field] for w in ref)/len(ref)
 comparisons[field]={'large_20_22T':last[field],'small_18_20T':ref[0][field],'small_20_22T':ref[1][field],'small_mean_18_22T':baseline,'delta_large_minus_small':last[field]-baseline,'formula':f'{last[field]} - ({ref[0][field]} + {ref[1][field]})/2'}
(R/'DIFFERENCE.json').write_text(json.dumps(comparisons,indent=2)+'\n')
with (R/'CORRELATION_DOMAIN8H.csv').open('x',newline='') as f:
 wr=csv.writer(f);wr.writerow(['window','direction','delta_m','R_uu'])
 for w in windows[-2:]:
  for axis in ('x','y'):
   for delta,val in w['correlation_curve'][f'{axis}_m'].items():wr.writerow([w['window'],axis,delta,val])
fig,ax=plt.subplots(3,2,figsize=(11,9));t=[2*w['window'] for w in windows]
for sub,field in zip(ax.flat,['V1_ratio','R_uu_x_half','R_uu_y_half','Px_mean','e_2p5','S2b_rms']):
 sub.plot(t,[w[field] for w in windows],'.-');sub.set(title=field,xlabel='end T');sub.grid(True,alpha=.25)
fig.tight_layout();fig.savefig(R/'WINDOW_TRENDS_DOMAIN8H.svg');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(12,4))
for a,axis in zip(ax,['x','y']):
 for w in windows[-2:]:
  c=w['correlation_curve'][f'{axis}_m'];a.plot([int(k) for k in c],[float(v) for v in c.values()],'.-',label=f"{2*w['window']-2}–{2*w['window']}T")
 a.axhline(0,color='gray',linewidth=.8);a.set(title=axis,xlabel='separation m',ylabel='R_uu');a.legend();a.grid(True,alpha=.25)
fig.tight_layout();fig.savefig(R/'CORRELATION_DOMAIN8H.svg');plt.close(fig)
print(json.dumps({'windows':len(windows),'last':{k:last[k] for k in ['e_2p5','S2b_rms']},'comparison':comparisons},ensure_ascii=False))
