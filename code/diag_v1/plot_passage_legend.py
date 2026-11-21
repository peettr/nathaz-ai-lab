import csv,pathlib,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pathlib.Path(__file__).resolve().parent;c=list(csv.DictReader(open(P/'passage_coast_v1.csv')));q=list(csv.DictReader(open(P/'passage_conditional_v1.csv')))
segs=['TX','LA_to_Panhandle','FL_peninsula','Carolinas'];fig,ax=plt.subplots(1,2,figsize=(12,5));xx=np.arange(4);width=.23
for j,(src,period) in enumerate([('RAFT','all'),('STORM','all'),('HURDAT2','1988-2018')]):
 y=[float(next(r for r in c if (r['source'],r['period'],r['segment'],r['zone'],r['threshold'])==(src,period,seg,'km_le100','Cat3+'))['mean_per_year']) for seg in segs]
 v=[float(next(r for r in q if (r['source'],r['period'],r['segment'],r['zone'],r['threshold'])==(src,period,seg,'km_le100','TS'))['v_p90']) for seg in segs]
 bars=ax[0].bar(xx+(j-1)*width,y,width,label=src);ax[1].scatter(xx+(j-1)*width,v,label=src,color=bars.patches[0].get_facecolor(),s=48)
for a in ax:a.set_xticks(xx,segs,rotation=16);a.legend(loc='upper left',fontsize=8)
ax[0].set_ylabel('Cat3+ passages / site / year (≤100 km)');ax[1].set_ylabel('Passage vmax p90 (kt), TS+ ≤100 km')
fig.text(.5,.012,'Sources: RAFT Xu 2024; STORM v4 4TU; HURDAT2 NHC 2026; EBTRK CIRA. Native nodes, not model winds.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.045,1,1));fig.savefig(P/'passage_v1_legend.png',dpi=170);plt.close(fig)
