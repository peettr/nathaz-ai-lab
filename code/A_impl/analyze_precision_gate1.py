"""Read small Colab summaries only. Never execute a solver locally."""
from pathlib import Path
import json,csv,io,math
b=Path(__file__).resolve().parent
names=('none','first','second','filtered')
data={n:json.loads((b/(n+'_profile.json')).read_text()) for n in names}
with (b/'precision_gate1_profiles.csv').open('w',newline='') as out:
 w=csv.writer(out);w.writerow(['case','x_m','z_m','U_over_Uin','deviation_percent','U_mps'])
 for n,d in data.items():
  for r in d['rows']:
   if r['x'] in (200,300,400) and 2<=r['z']<=20:w.writerow([n,r['x'],r['z'],f"{r['ratio']:.8f}",f"{100*(r['ratio']-1):.5f}",f"{r['speed']:.8f}"])
results={}
for n,d in data.items():
 rows=d['rows'];s={x:{z:next(r for r in rows if r['x']==x and r['z']==z) for z in range(2,21)} for x in (200,300,400)}
 ratios={str(x):s[x][2]['ratio'] for x in s};profile_max=max(abs(r['ratio']-1) for x in s for r in s[x].values())
 entry=dict(u2=ratios,max_deviation_2_20=profile_max,profile_fails_systematic_sign=all(s[x][2]['ratio']<1 for x in s) and all(s[x][z]['ratio']>1 for x in s for z in (5,10,15,20)))
 if d['wall_tau_csv']:
  wallpoints=list(csv.DictReader(io.StringIO(d['wall_tau_csv'])))
  entry['ustar_ratio']={str(x):sum(float(p['ustar_mps']) for p in wallpoints if int(p['x'])==x)/5/.2418545 for x in (200,300,400)}
  entry['tau_count_values']=sorted({int(float(p['count'])) for p in wallpoints})
  fx=sum(float(row['fx_over_rho_lattice_sum']) for row in d['wall_x'])
  rho_si=1.225;wall_si=fx*rho_si/d['unit_u_lattice_per_si']**2
  a=d['flux100'];c=d['flux400'];top=d['top'];adv=a['adv']-c['adv'];p=a['pres']-c['pres'];t=top['adv'];net=adv+p-t
  entry['cv_partial']=dict(face_adv_in_minus_out=adv,face_pressure_in_minus_out=p,top_adv_out=t,wall_force_x_estimated_SI=wall_si,net_with_wall=net+wall_si,residual_percent_abswall=100*abs(net+wall_si)/abs(wall_si),face_tke_upper_proxy_in_minus_out=a['tke_upper_proxy']-c['tke_upper_proxy'],top_tke_upper_proxy=top['tke_upper_proxy'],wall_columns_valid=sum(int(row['columns']) for row in d['wall_x']),wall_columns_possible=301*198,assumptions='rho_si=1.225 kg/m3, uconvert=0.1/3.9286416; pressure rho*c_s^2; only mean-flow flux and x-face pressure; y-face, resolved Reynolds, SGS/viscous, pressure fluctuation, storage not included')
 results[n]=entry
(b/'precision_gate1_metrics.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
