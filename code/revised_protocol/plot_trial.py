"""Plot revised cold-season trial, not a formal ensemble validation."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'seasonal_trial.csv').open()))
labels=[r['site'] for r in rows]
keys=['median_bias_pct','p90_bias_pct','gev_50yr_bias_pct','pot_50yr_bias_pct']
fig,ax=plt.subplots(figsize=(10,5.5))
x=np.arange(len(rows));width=.2
for j,key in enumerate(keys):
    ax.bar(x+(j-1.5)*width,[float(r[key]) for r in rows],width,label=key.replace('_bias_pct',''))
ax.axhline(20,color='firebrick',ls=':',label='±20% flag (both signs)')
ax.axhline(-20,color='firebrick',ls=':')
ax.axhline(10,color='grey',ls='--',alpha=.5)
ax.axhline(-10,color='grey',ls='--',alpha=.5)
ax.set_xticks(x,labels);ax.set_ylabel('(ACE2 / ERA5 − 1) × 100%')
ax.set_title('Oct–Mar 1979/80–2007/08: 29 complete seasons, SINGLE rollout (trial only)')
ax.legend(ncol=3,fontsize=8);ax.grid(axis='y',alpha=.2)
fig.text(.01,.01,'Source: ACE2-ERA5 (Ai2) 10m U/V; ERA5 via WeatherBench2 1.5° conservative → 1° linear. 6-hourly; no event-type filtering.',fontsize=8)
fig.tight_layout(rect=(0,.045,1,1))
fig.savefig(p/'cold_season_trial.png',dpi=160)
print('PLOT_DONE',p/'cold_season_trial.png')
