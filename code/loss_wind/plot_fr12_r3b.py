#!/usr/bin/env python3
"""Plot the existing r3 point table without rerunning reconstruction; never overwrite."""
from pathlib import Path
import csv,collections,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent; target=P/'fr12_trend_r3b.png'
if target.exists():raise FileExistsError(target)
rows=[r for r in csv.DictReader((P/'dat_hurricane_points_r3.csv').open()) if 'FR12' in (r['damage_type'] or '') and r['model_gust_mps'] and r['dod']]
fig,ax=plt.subplots(1,2,figsize=(12,4.8))
colors={'IDA':'#1f77b4','IDALIA':'#ff7f0e','HELENE':'#2ca02c'}
for name,color in colors.items():
 subset=[r for r in rows if r['event']==name]
 ax[0].scatter([float(r['model_gust_mps']) for r in subset],[float(r['dod']) for r in subset],c=color,s=20,alpha=.5,label=f'{name} n={len(subset)}')
ax[0].legend(title='Hurricane',fontsize=8);ax[0].set(xlabel='Reconstructed peak gust (m/s; not measured)',ylabel='FR12 DOD code',title='DAT one-/two-family residences (FR12)')
bins=[0,15,20,25,30,35,40,50,70,200];group=collections.defaultdict(list)
for r in rows:
 x=float(r['model_gust_mps']);d=float(r['dod'])
 for lo,hi in zip(bins,bins[1:]):
  if lo<=x<hi:group[(lo,hi)].append((x,d));break
for (lo,hi),a in sorted(group.items()):
 x=float(np.median([t[0] for t in a]));y=float(np.median([t[1] for t in a]))
 ax[1].scatter([x],[y],s=max(20,len(a)*7),color='#303030',alpha=.75)
 ax[1].annotate(f'{len(a)}',xy=(x,y),xytext=(0,10),textcoords='offset points',ha='center',fontsize=8)
ax[1].set(xlabel='Median actual wind in each bin (m/s)',ylabel='Median FR12 DOD code (labels = count)',title='Bins: [0,15,20,25,30,35,40,50,70,200) m/s')
for a in ax:a.set_xlim(8,85);a.set_ylim(.6,4.45);a.grid(alpha=.2)
fig.text(.5,.01,'NWS DAT damage points + H2 NHC/ATCF/IEM wind reconstruction; peaks may be underestimated. Damaged-only selection, not a probability curve.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(target,dpi=160)
print(target,len(rows),{str(k):len(v) for k,v in group.items()})
