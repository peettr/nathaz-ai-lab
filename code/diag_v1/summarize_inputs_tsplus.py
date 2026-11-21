"""Matched TS-or-stronger native-node summaries; supersedes unaligned diagnostic table."""
import csv,pathlib,numpy as np
P=pathlib.Path(__file__).resolve().parent
obs=list(csv.DictReader(open(P/'obs_inputs.csv')));syn=list(csv.DictReader(open(P/'inputs_land.csv')))
def q(vals):
 a=np.array([float(v) for v in vals if v not in ('',None)]);a=a[np.isfinite(a)]
 return dict(n=len(a),p01=float(np.quantile(a,.01)) if len(a) else None,p10=float(np.quantile(a,.10)) if len(a) else None,p50=float(np.quantile(a,.5)) if len(a) else None,p90=float(np.quantile(a,.9)) if len(a) else None,p99=float(np.quantile(a,.99)) if len(a) else None)
for r in obs:
 r['catalog']='HURDAT2+EBTRK';r.update(vmax_kt=r['vmax'],pc_hpa=r['pc'],dp1010_hpa=str(max(0,1010-float(r['pc']))) if r['pc'] else '',rmw_nmi=r['rmw'])
 r['land']='land' if r['land_km'] and float(r['land_km'])<0 else ('sea' if r['land_km'] else 'missing')
rows=[r for r in syn+obs if float(r['vmax_kt'])>=35]
for r in rows:
 v=float(r['vmax_kt']);r['intensity']='TS' if v<64 else 'Cat1-2' if v<96 else 'Cat3+'
out=[]
for cat in ('RAFT','STORM','HURDAT2+EBTRK'):
 for strength in ('ALL','TS','Cat1-2','Cat3+'):
  for land in ('ALL','sea','land'):
   g=[r for r in rows if r['catalog']==cat and (strength=='ALL' or r['intensity']==strength) and (land=='ALL' or r['land']==land)]
   for col in ('vmax_kt','pc_hpa','dp1010_hpa','rmw_nmi'):
    out.append(dict(catalog=cat,intensity=strength,land=land,variable=col,**q([r[col] for r in g])))
with open(P/'input_summary_tsplus.csv','x') as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
print([(c,q([r['vmax_kt'] for r in rows if r['catalog']==c])) for c in ('RAFT','STORM','HURDAT2+EBTRK')])
