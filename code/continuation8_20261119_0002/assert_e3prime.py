#!/usr/bin/env python3
"""E3-prime: replay actual previous-step velocity and device epsilon, fail closed."""
import argparse,csv,json,math,statistics,sys
from collections import defaultdict
P=argparse.ArgumentParser();P.add_argument('trace');P.add_argument('evolution');P.add_argument('--top',required=True);P.add_argument('--comparison');a=P.parse_args()
rows=list(csv.DictReader(open(a.trace))); evolution=list(csv.DictReader(open(a.evolution)))
top_rows=list(csv.DictReader(open(a.top)))
assert top_rows and [int(r['step']) for r in top_rows]==list(range(len(top_rows)))
top_delta=max(abs(float(r['delta_ux'])) for r in top_rows)
top_proxy=max(abs(float(r['top_shear_proxy'])) for r in top_rows)
assert top_delta<=1e-8 and top_proxy<=2e-10,('top zero-gradient failed',top_delta,top_proxy)
assert rows and evolution
steps={int(r['step']) for r in rows}; last=max(steps)
coords={(int(r['x']),int(r['y'])) for r in rows}
assert len(coords)>=64 and steps==set(range(last+1)) and len(rows)==len(coords)*(last+1)
assert [int(r['step']) for r in evolution]==list(range(1,last+1))
by_step=defaultdict(dict)
for r in rows:
 key=(int(r['x']),int(r['y']));step=int(r['step']);assert key not in by_step[step];by_step[step][key]=r
 def number(k):
  v=float(r[k]);assert math.isfinite(v),(step,key,k);return v
 for name in ('tau_f_x_lattice','tau_f_y_lattice','tau_f_abs_lattice','applied_force_x_lattice','applied_force_y_lattice','area_lattice','match_ux_previous','match_uy_previous','match_rho_previous','epsilon_device','match_speed_lattice','tau_w_theory_lattice','relative_error'):number(name)
assert all(set(by_step[t])==coords for t in steps)
logwall=math.log((1.5+0.024)/0.024);prev={key:(float(by_step[0][key]['tau_f_x_lattice']),float(by_step[0][key]['tau_f_y_lattice'])) for key in coords}
relative=[];force=[];comparison=[]; nonzero=0;total=0
for t in range(1,last+1):
 ev=evolution[t-1];epsilon=float(ev['epsilon_device']);mean=float(ev['mean_match_speed']);tf=float(ev['Tf_steps']);assert 0<epsilon<=1 and abs(epsilon-min(1,max(0,mean*.1)))<1e-6 and abs(tf-1/epsilon)<1e-5*tf
 for key in sorted(coords):
  r=by_step[t][key];assert abs(float(r['epsilon_device'])-epsilon)<1e-8
  vx=float(r['match_ux_previous']);vy=float(r['match_uy_previous']);rho=float(r['match_rho_previous']);speed=math.hypot(vx,vy);tau=rho*(.4*speed/logwall)**2
  assert rho>0 and abs(float(r['match_speed_lattice'])-speed)<1e-8 and abs(float(r['tau_w_theory_lattice'])-tau)<max(1e-10,1e-5*tau)
  target=(tau*vx/speed,tau*vy/speed) if speed>1e-8 else (0.,0.)
  replay=tuple(prev[key][i]+epsilon*(target[i]-prev[key][i]) for i in (0,1));prev[key]=replay
  actual=(float(r['tau_f_x_lattice']),float(r['tau_f_y_lattice']));mag=math.hypot(*actual)
  err=math.hypot(*(actual[i]-replay[i] for i in (0,1)))/max(mag,math.hypot(*replay),1e-20)
  relative.append(err)
  area=float(r['area_lattice']);assert area>0
  ferr=math.hypot(float(r['applied_force_x_lattice'])+area*actual[0],float(r['applied_force_y_lattice'])+area*actual[1])/max(area*mag,1e-20)
  force.append(ferr);nonzero+=mag>0;total+=1
  if a.comparison:comparison.append((t,*key,replay[0],replay[1],*actual,err,ferr))
if a.comparison:
 with open(a.comparison,'x',newline='') as f:
  w=csv.writer(f);w.writerow(['step','x','y','replay_x','replay_y','device_x','device_y','relative_error','force_relative_error']);w.writerows(comparison)
window=math.ceil(float(evolution[-1]['Tf_steps']));steady=last>=5*window and last>window
speeds=[float(r['mean_match_speed']) for r in evolution]
drift=abs(speeds[-1]-speeds[-1-window])/max(abs(speeds[-1]),1e-20) if steady else None
steady=steady and drift<=.01
recent=[by_step[t][key] for t in range(max(1,last-window+1),last+1) for key in coords]
tau_mean=statistics.fmean(float(r['tau_f_abs_lattice']) for r in recent)
theory_mean=statistics.fmean(float(r['tau_w_theory_lattice']) for r in recent)
ratio=tau_mean/theory_mean if theory_mean>0 else None
result={'rows':len(rows),'columns':len(coords),'last_step':last,'Tf_steps':window,'window_deltaU_over_U':drift,'nonzero_fraction':nonzero/total,'replay_relative_median':statistics.median(relative),'replay_relative_max':max(relative),'force_relative_max':max(force),'tau_f_last_Tf_mean':tau_mean,'tau_w_last_Tf_mean':theory_mean,'steady_ratio':ratio,'momentum_balance_tau_over_FH_descriptive':tau_mean/(1e-6*10),'top_imposed_max_delta_ux':top_delta,'top_imposed_max_viscous_shear_proxy':top_proxy}
result['gates']={'nonzero':result['nonzero_fraction']>=.99,'replay':result['replay_relative_median']<=1e-4 and result['replay_relative_max']<=1e-3,'force':result['force_relative_max']<=1e-6,'steady':bool(steady and ratio is not None and .8<=ratio<=1.2)}
result['verdict']='PASS' if all(result['gates'].values()) else ('INDETERMINATE_NOT_STEADY' if not steady else 'FAIL')
print(json.dumps(result,sort_keys=True),flush=True)
sys.exit(0 if result['verdict']=='PASS' else 2)
