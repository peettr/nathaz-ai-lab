from pathlib import Path
import json,csv,math
R=Path(__file__).resolve().parent
p=R.parent/'approach_z0/stage_FG0z/case/wind_bc/profile.dat'
profile=[]
for line in p.read_text().splitlines()[1:]:
 z,u=map(float,line.split());profile.append((z,u))
def official(z):
 if z<profile[0][0]:return profile[0][1]
 for (z0,u0),(z1,u1) in zip(profile,profile[1:]):
  if z0<=z<=z1:return u0+(z-z0)/(z1-z0)*(u1-u0)
 raise ValueError(z)
result={};prof=[];rows=[]
for tag in ('FGz2','FGz6'):
 d=json.loads((R/(tag+'_samples.json')).read_text())
 assert d['dimensions'][:2]==[500,500],d['dimensions']
 assert (R/(tag+'_solver.exit')).read_text().startswith('0 None')
 by={(float(q['x']),float(q['z_agl'])):q for q in d['profiles']}
 up={(float(q['x_local_m']),float(q['z_m'])):q for q in d['upstream']}
 for q in d['profiles']:
  prof.append({'tag':tag,'x_m':q['x'],'z_m':q['z_agl'],'U_mps':q['U_mps'],'k_m2s2':q['k_m2s2'],'official_U_mps':official(q['z_agl']),'bias_pct':100*(q['U_mps']/official(q['z_agl'])-1)})
 vals={}
 for x in (5,42,120,200):
  vals[str(x)]={}
  for z in (2,5,10,15.9):
   q=up[x,z];u=float(q['mean_speed_mps']);ref=official(z);k=float(by[x,z]['k_m2s2']) if z!=15.9 else None
   vals[str(x)][str(z)]={'U_mps':u,'official_mps':ref,'bias_pct':100*(u/ref-1),'k_m2s2':k}
   rows.append({'tag':tag,'x_m':x,'z_m':z,'U_mps':u,'official_mps':ref,'bias_pct':100*(u/ref-1),'k_m2s2':k})
 gate_bias=[vals[str(x)][str(z)]['bias_pct'] for x in (42,120,200) for z in (2,5,10,15.9)]
 amplitude=all(abs(v)<=5 for v in gate_bias)
 antiphase=[]
 for x in (42,120,200):
  a=vals[str(x)]['2']['bias_pct'];b=[vals[str(x)][str(z)]['bias_pct'] for z in (5,10)]
  antiphase.append({'x':x,'bad':a<0 and any(v>0 and v-a>5 for v in b),'lower':a,'upper':b})
 trace=list(csv.DictReader((R/(tag+'_trace.csv')).open()));assert int(trace[-1]['step'])==31000
 result[tag]={'values':vals,'gate_amplitude':amplitude,'gate_antiphase':antiphase,'gate_pass':amplitude and not any(q['bad'] for q in antiphase),'ustar':json.loads((R/(tag+'_ustar.json')).read_text()),'trace':{'rows':len(trace),'max_u':max(float(q['max_u_lattice']) for q in trace),'min_rho_after_3000':min(float(q['min_rho']) for q in trace if int(q['step'])>=3000),'max_rho_after_3000':max(float(q['max_rho']) for q in trace if int(q['step'])>=3000)}}
with (R/'profiles_z0b.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=prof[0]);w.writeheader();w.writerows(prof)
with (R/'gate_z0b.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(R/'metrics_z0b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
