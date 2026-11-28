import csv,pathlib,json,numpy as np
P=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader(open(P/'obs_inputs.csv')))
def q(vals):
 a=np.array([float(v) for v in vals if v!='' and np.isfinite(float(v))]);return dict(n=len(a),p50=round(float(np.quantile(a,.5)),2),p90=round(float(np.quantile(a,.9)),2),p99=round(float(np.quantile(a,.99)),2)) if len(a) else dict(n=0,p50=None,p90=None,p99=None)
def grp(r):
 v=int(r['vmax']);return 'TS' if v<64 else 'Cat1-2' if v<96 else 'Cat3+'
def coast(r):
 d=float(r['land_km']) if r['land_km']!='' else np.nan
 return 'land' if d<0 else ('sea' if d>=0 else 'missing')
out=[]
for group in ['ALL','TS','Cat1-2','Cat3+']:
 for zone in ['ALL','land','sea']:
  s=[r for r in rows if (group=='ALL' or grp(r)==group) and (zone=='ALL' or coast(r)==zone)]
  if not s:continue
  for name,values in [('vmax_kt',[r['vmax'] for r in s]),('Pc_hPa',[r['pc'] for r in s]),('DP1010_hPa',[str(max(0,1010-float(r['pc']))) for r in s if r['pc']!='']),('RMW_nmi',[r['rmw'] for r in s])]:
   out.append(dict(catalog='HURDAT2+EBTRK',intensity=group,land=zone,variable=name,**q(values)))
with open(P/'obs_summary.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
x=np.array([float(r['vmax']) for r in rows if r['pc']!='']);y=np.array([float(r['pc']) for r in rows if r['pc']!=''])
coeff=np.polyfit(x,y,2)
# Quadratic fit is a diagnostic predictor. Do not infer environmental pressure from the intercept.
cat=np.array([v>=114 for v in x]);raft=1030.222-.730*x
print(json.dumps(dict(obs_points=len(rows),rmw_valid=sum(r['rmw']!='' for r in rows),quad_pc_coeff=coeff.tolist(),cat45_n=int(cat.sum()),cat45_raft_pc_bias_median_hPa=float(np.median(raft[cat]-y[cat])),cat45_observed_vmax_median_kt=float(np.median(x[cat]))),indent=2))
