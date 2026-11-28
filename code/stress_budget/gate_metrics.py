from pathlib import Path
import csv,json,io,math,statistics
b=Path(__file__).resolve().parent
cases={'baseline':'diagnostic_profile.json','mixing_full':'mixing_profile.json','mixing_70pct':'mixing07_profile.json'}
rows=[]
for name,file in cases.items():
 d=json.loads((b/file).read_text());wall=list(csv.DictReader(io.StringIO(d['wall_tau_csv'])))
 for x in (200,300,400):
  p={z:next(r for r in d['rows'] if r['x']==x and r['z']==z)['ratio'] for z in range(2,21)}
  st=statistics.mean(float(v['ustar_mps']) for v in wall if int(v['x'])==x)
  rows.append(dict(case=name,x=x,u2_ratio=p[2],u5_ratio=p[5],u10_ratio=p[10],u20_ratio=p[20],max_deviation=max(abs(r-1) for r in p.values()),ustar=st,ustar_ratio=st/.2418545,shifted_u2_ratio=p[2]*math.log((2+.024)/.024)/math.log((1.5+.024)/.024),opposite_sign=(p[2]<1 and p[5]>1 and p[10]>1 and p[20]>1)))
with (b/'gate_metrics.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print(*rows,sep='\n')
