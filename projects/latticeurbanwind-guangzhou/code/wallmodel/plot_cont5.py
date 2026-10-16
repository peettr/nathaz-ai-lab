"""Compare 0–60 m profiles and x trends from the same empty-field setup."""
from pathlib import Path
import json,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path(__file__).resolve().parent
files={'off':r/'cont5_off_profile.json','first':r/'cont5_on_first_profile.json','damped':r/'cont5_damped_profile.json'}
data={k:json.loads(p.read_text())['rows'] for k,p in files.items()}
colors={'off':'#777777','first':'#1967a3','damped':'#d87025'}
z0=.024;uref=3.9286416
fig,ax=plt.subplots(1,2,figsize=(11,5))
for x in (100,200,300,400):
 for k,rows in data.items():
  q=sorted((v for v in rows if v['x']==x and v['z']>=2),key=lambda v:v['z'])
  ax[0].plot([v['speed'] for v in q],[v['z'] for v in q],color=colors[k],alpha=.35 if x!=300 else 1,lw=1 if x!=300 else 2,label=f'{k} x={x}' if x==300 else None)
for reference in ('z','z_minus_half'):
 zs=list(range(2,61));ref=[uref*math.log(((z-(.5 if reference=='z_minus_half' else 0))+z0)/z0)/math.log((15.9+z0)/z0) for z in zs]
 ax[0].plot(ref,zs,'--' if reference=='z' else ':',lw=1.4,label='log reference '+reference)
for k,rows in data.items():
 for x in (100,200,300,400):
  p={v['z']:v for v in rows if v['x']==x};ax[1].plot(x,p[2]['speed']/uref,'o',color=colors[k],alpha=.35 if x!=300 else 1)
 q=[v for v in rows if v['z']==2 and 100<=v['x']<=400];ax[1].plot([v['x'] for v in q],[v['ratio'] for v in q],'-',color=colors[k],label=k)
ax[0].set(yscale='log',ylim=(2,60),xlabel='mean speed (m/s)',ylabel='physical z (m)',title='Empty-field profiles, five lateral stations averaged');ax[0].legend(fontsize=7)
ax[1].set(xlabel='distance from inlet (m)',ylabel='U(2 m) / inlet U(2 m)',title='Near-ground development');ax[1].axhspan(.85,1.05,color='green',alpha=.12);ax[1].legend()
for a in ax:a.grid(alpha=.25)
fig.tight_layout();fig.savefig(r/'empty_profiles_cont5.png',dpi=175)
print('saved',r/'empty_profiles_cont5.png')
