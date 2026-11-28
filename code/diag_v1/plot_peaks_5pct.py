"""Paired 5% event sample H08 site-peak sensitivity visualization."""
import csv,pathlib,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader(open(P/'peak_summary_5pct.csv')));names=[r['site'] for r in csv.DictReader(open(P/'sites_min.csv'))]
fig,ax=plt.subplots(2,1,figsize=(12,7.6),sharex=True)
colors={'base':'#333333','Pc_only':'#2475b8','RMW_only':'#ed8c2b','both':'#2a9d70'}
for k,cat in enumerate(('RAFT','STORM')):
 for j,variant in enumerate(('base','Pc_only','RMW_only','both')):
  vals=[next(float(r['peak_p90']) for r in rows if r['catalog']==cat and r['site']==site and r['variant']==variant) for site in names]
  ax[k].plot(np.arange(len(names)),vals,marker='o',ms=3,label=variant,color=colors[variant],alpha=.8)
 ax[k].set_title(cat+' — 90th percentile of positive (>5 m/s baseline) single-event site peaks');ax[k].set_ylabel('Peak wind (m/s, same H08 + 1.07)');ax[k].grid(alpha=.2)
ax[0].legend(ncol=4,fontsize=8,loc='upper right');ax[-1].set_xticks(np.arange(len(names)),names,rotation=45,ha='right');fig.tight_layout(rect=(0,.045,1,1))
fig.text(.01,.008,'Sources: RAFT (Xu 2024), STORM v4 (Bloemendaal 2020), HURDAT2 + EBTRK; CLIMADA 6.1.0 H08. Deterministic 5% event sample; NOT return levels.',fontsize=8)
fig.savefig(P/'paired_peak_5pct.png',dpi=155);print(P/'paired_peak_5pct.png')
