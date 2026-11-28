from pathlib import Path
import csv,json,math,hashlib
R=Path(__file__).resolve().parent
new={(int(r['x']),int(r['z_agl_m'])):r for r in csv.DictReader((R/'FGz2c_planes.csv').open())}
old={(int(r['x']),int(r['z_agl_m'])):r for r in csv.DictReader((R.parent/'inflow_sponge/FGz2r_planes.csv').open())}
O={2:2.964,5:3.2604,10:3.588,15.9:3.9286416}
def interp(a,x,z,key='U_mps'):
 if z==int(z):return float(a[x,int(z)][key])
 return float(a[x,15][key])*.1+float(a[x,16][key])*.9
rows=[]
for x in (5,42,120,200,300):
 for z,target in O.items():
  u=interp(new,x,z);v=interp(old,x,z)
  rows.append({'x_m':x,'z_m':z,'official_mps':target,'FGz2r_mps':v,'FGz2c_mps':u,'FGz2r_bias_pct':100*(v/target-1),'FGz2c_bias_pct':100*(u/target-1),'change_mps':u-v})
with (R/'gate_precorrect.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
trace=list(csv.DictReader((R/'FGz2c_trace.csv').open()))
assert trace and int(trace[-1]['step'])==31000
summ={'gate_rows':rows,'stability':{'samples':len(trace),'last_step':int(trace[-1]['step']),'max_u':max(float(q['max_u_lattice']) for q in trace),'rho_min_after3000':min(float(q['min_rho']) for q in trace if int(q['step'])>=3000),'rho_max_after3000':max(float(q['max_rho']) for q in trace if int(q['step'])>=3000),'nonfinite':sum(bool(q['first_nonfinite_xyz_component']) for q in trace)},'CU_estimate':(24*60+31)*5.4/3600}
(R/'metrics.json').write_text(json.dumps(summ,indent=2)+'\n')
print('CU',summ['CU_estimate'],'stability',summ['stability'])
for x in (42,120,200):print(x,[round(q['FGz2c_bias_pct'],2) for q in rows if q['x_m']==x])
