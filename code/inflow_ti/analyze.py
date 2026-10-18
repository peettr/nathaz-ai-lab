from pathlib import Path
import json,statistics,csv,math
R=Path(__file__).resolve().parent
base=json.loads(Path('./24_Urban_Wind_LBM/06_Logs/wp1_nearwall/city_stab/stage6noT_offset_samples_a_r10.json').read_text())
points=json.loads(Path('./22_Lab/06_Logs/luw/run_r10_20261014/points_w_r7.json').read_text())
k_tab=[(1.25,.008),(2.5,.009),(5,.009),(7.5,.009),(12.5,.010),(25,.010),(50,.009),(75,.008),(100,.007),(150,.006),(200,.004),(250,.002)]
def official_k(z):
 if z<=k_tab[0][0]:return k_tab[0][1]*7.8**2
 if z>=250:return k_tab[-1][1]*7.8**2
 for (z0,k0),(z1,k1) in zip(k_tab,k_tab[1:]):
  if z<=z1:return (k0+(k1-k0)*(z-z0)/(z1-z0))*7.8**2
 raise ValueError(z)
out={};prows=[]
for tag in 'AB':
 name='B2' if tag=='B' else 'A'
 d=json.loads((R/f'{name}_offset_samples.json').read_text());trace=list(csv.DictReader((R/f'{name}_trace.csv').open()));
 assert len(d['rows'])==80 and int(trace[-1]['step'])==31000
 out[tag]={'trace':{'n':len(trace),'last':trace[-1]['step'],'max_speed':max(float(v['max_u_lattice']) for v in trace),'rho_post3000':[min(float(v['min_rho']) for v in trace if int(v['step'])>=3000),max(float(v['max_rho']) for v in trace if int(v['step'])>=3000)]},'metrics':{}}
 for label,ids in [('all',set(range(1,81))),('wall',{50,51,52,54}),('open',{23,25,37,17})]:
  rows=[r for r in d['rows'] if r['id'] in ids];obs=[r['after'] for r in rows]
  out[tag]['metrics'][label]={}
  for q in ('sim_ratio','exp_ratio'):
   vals=[r['sample']['plus_dx'][q] for r in rows]
   out[tag]['metrics'][label][q]={'mae':statistics.mean(abs(x-y) for x,y in zip(vals,obs)),'r':statistics.correlation(vals,obs),'mean_ratio':statistics.mean(vals)/statistics.mean(obs)}
 out[tag]['points']={str(i):next(r for r in d['rows'] if r['id']==i) for i in [50,51,52,54,23,25,37,17]}
 out[tag]['upwind']={str(x):next(q for q in d['upstream'] if q['x_local_m']==x and q['z_m']==2.)['fraction_input'] for x in (25.,42.)}
 line=d['street50'];segments=[];start=None
 for j,v in enumerate(line):
  backward=v['ux']<0 and v['fluid_corners']==8
  if backward and start is None:start=v['x']
  if not backward and start is not None:segments.append((start,line[j-1]['x']));start=None
 if start is not None:segments.append((start,line[-1]['x']))
 out[tag]['street50_negative_ux_segments']=segments
 for row in d['profiles']:
  x,z=row['x'],row['z_agl'];prows.append({'run':tag,'x_m':x,'z_m':z,'mean_U_mps':row['U_mps'],'resolved_k_m2s2':row['k_m2s2'],'official_inflow_k_m2s2':official_k(z),'ratio_to_official':row['k_m2s2']/official_k(z)})
(R/'profiles_comparison.csv').write_text(''.join([]))
with (R/'profiles_comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=prows[0]);w.writeheader();w.writerows(prows)
(R/'summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:{'trace':v['trace'],'metrics':v['metrics']['all'],'upwind':v['upwind'],'street':v['street50_negative_ux_segments']} for k,v in out.items()},indent=2))
