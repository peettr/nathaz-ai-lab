"""Input-only quantile charts, no standards data or return levels."""
import csv,pathlib,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pathlib.Path(__file__).resolve().parent
series={}
for name,path in [('RAFT',P/'raft_inputs_checkpoint.csv'),('STORM',P/'inputs_raw.csv'),('HURDAT2+EBTRK',P/'obs_inputs.csv')]:
 rows=list(csv.DictReader(open(path)))
 if name=='STORM':rows=[r for r in rows if r['catalog']=='STORM']
 v=np.array([float(r['vmax_kt'] if name!='HURDAT2+EBTRK' else r['vmax']) for r in rows]);pc=np.array([float(r['pc_hpa'] if name!='HURDAT2+EBTRK' else r['pc']) for r in rows]);rm=np.array([float(r['rmw_nmi'] if name!='HURDAT2+EBTRK' else r['rmw']) if (r['rmw_nmi'] if name!='HURDAT2+EBTRK' else r['rmw'])!='' else np.nan for r in rows]);series[name]=(v,pc,rm)
fig,ax=plt.subplots(1,2,figsize=(12,4.7));bins=np.arange(35,166,10);colors={'RAFT':'#2667a7','STORM':'#e3862f','HURDAT2+EBTRK':'#1c7754'}
for name,(v,pc,rm) in series.items():
 for j,field in enumerate((pc,rm)):
  points=[]
  for b in bins:
   vals=field[(v>=b-5)&(v<b+5)&np.isfinite(field)];points.append((np.median(vals),np.quantile(vals,.1),np.quantile(vals,.9)) if len(vals)>=10 else (np.nan,)*3)
  y=np.array(points);ax[j].plot(bins,y[:,0],marker='o',ms=3,label=name,color=colors[name]);ax[j].fill_between(bins,y[:,1],y[:,2],alpha=.11,color=colors[name])
ax[0].set_ylabel('Central pressure Pc (hPa)');ax[1].set_ylabel('Radius of max wind (nmi)')
for a in ax:a.set_xlabel('Track vmax (kt; STORM 10-min converted ×1.11)');a.grid(alpha=.25)
ax[0].legend(fontsize=8);fig.suptitle('Input distributions near 19 coastal sites (≤500 km)')
fig.text(.01,.008,'Sources: Xu et al. 2024 RAFT; Bloemendaal et al. 2020 STORM v4; NHC HURDAT2 2026 + CIRA EBTRK v3.0.2. Native track nodes; shading P10–P90.',fontsize=8)
fig.tight_layout(rect=(0,.035,1,.98));fig.savefig(P/'inputs_comparison.png',dpi=160);print(P/'inputs_comparison.png')
