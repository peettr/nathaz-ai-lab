"""Combine retained six-cell series with DFW/AUS results; never overwrite originals."""
from pathlib import Path
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('/content/dfw_aus_analysis');old=Path('/content/old_six');root.mkdir(exist_ok=True)
a=pd.read_csv(old/'metrics.csv');b=pd.read_csv(root/'metrics_dfw_aus.csv')
assert len(a)==6 and len(b)==2 and not set(a.station_anchor)&set(b.station_anchor)
df=pd.concat([a,b],ignore_index=True)
df.to_csv(root/'metrics_eight.csv',index=False,float_format='%.5f')
plt.rcParams.update({'font.size':10})
fig,axs=plt.subplots(1,3,figsize=(18,5))
for ax,key,title in zip(axs,['annual_max_median','annual_max_p90','gumbel_50yr'],['Annual maxima: median','Annual maxima: p90','Gumbel 50-year return level']):
 x=np.arange(len(df));ax.plot(x,df[f'era_{key}'],'o-',label='ERA5 (WB2 1.5° → ACE2)');ax.plot(x,df[f'ace_{key}'],'s-',label='ACE2-ERA5');ax.set_xticks(x,df.station_anchor,rotation=40);ax.set_title(title);ax.set_ylabel('10 m wind speed (m/s)');ax.grid(alpha=.25)
 for j,r in df.iterrows():ax.annotate(f'{r[key+"_bias_pct"]:+.0f}%',(j,r[f'ace_{key}']),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
axs[0].legend(loc='lower left',fontsize=8)
fig.suptitle('6-hourly 10-m wind, 1979–2008 (30 years; eight selected grid cells)')
fig.text(.01,.01,'Source: ACE2-ERA5 (Ai2 HF, historical forcing) vs ERA5 (Google WeatherBench2 1959–2022 1.5° conservative, bilinear to ACE2). Exploratory; not station gusts.',fontsize=8)
fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(root/'annual_max_comparison_eight.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(2,4,figsize=(18,8),sharex=True,sharey=True)
for ax,(_,r) in zip(axs.ravel(),df.iterrows()):
 p=(old if r.station_anchor not in ('DFW','AUS') else root)/f'points_{r.station_anchor}.npz'
 z=np.load(p);bins=np.arange(0,36,.5)
 ax.hist(z['era'],bins=bins,density=True,histtype='step',linewidth=1.6,label='ERA5');ax.hist(z['ace'],bins=bins,density=True,histtype='step',linewidth=1.6,label='ACE2');ax.set_title(f'{r.station_anchor} (mean bias {r.mean_speed_bias_pct:+.1f}%)');ax.grid(alpha=.2)
axs[0,0].legend();fig.supxlabel('6-hourly 10-m speed (m/s)',y=.06);fig.supylabel('Probability density');fig.suptitle('Whole speed distribution: ACE2 vs ERA5 (1979–2008)')
fig.text(.01,.008,'Source: ACE2-ERA5 (Ai2 HF) and ERA5 (Google WeatherBench2 1.5°); 6h vector magnitude; conservative+bilinear reference.',fontsize=8)
fig.tight_layout(rect=[.03,.12,1,.96]);fig.savefig(root/'speed_distribution_eight.png',dpi=160);plt.close(fig)
print('EIGHT_DONE',len(df), '50yr_bias',df[['station_anchor','gumbel_50yr_bias_pct']].to_dict('records'),flush=True)
