#!/usr/bin/env python3
"""Postprocess frozen T9b group-sum ratios from verified production points."""
import csv, hashlib, json, math, re
from pathlib import Path
R=Path(__file__).resolve().parent
LOGS=R.parents[1]
E=R/'run_luw-t9b17-a100-25014f15/evidence'
T5=LOGS/'R21.4a_T5_caseE_WM_retry2/evidence'
WIDTH=LOGS/'tacc_feasibility/T2c_post/widths.csv'
U=3.9286416
TARGET={'E_s101_off':'6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279','E_s102_off':'b284b8075072e0c162773096c4b7ba1547f0dc41517b461058803d16d82b8bcf'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verified(p):
 s=p.with_name(p.name+'.sha256');assert p.is_file() and s.is_file(),p
 d=digest(p);assert s.read_text().split()[0]==d,(p,d,s.read_text());return d
def points(p):
 d=json.loads(p.read_text());q={int(x['id']):x for x in d['rows']}
 assert len(d['rows'])==len(q)==80 and set(q)==set(range(1,81)) and d['uref']==U
 assert all(math.isfinite(x['Su']) and math.isfinite(x['obs']) and x['obs']>0 for x in q.values())
 return q
width={int(x['id']):x for x in csv.DictReader(WIDTH.open())};assert set(width)==set(range(1,81))
groups={'N':sorted(i for i,x in width.items() if float(x['width_min_m'])<15)}
groups['N_close']=[i for i in groups['N'] if float(width[i]['wall_m'])<1]
groups['N_far']=[i for i in groups['N'] if i not in groups['N_close']]
groups['wide']=[i for i in width if i not in groups['N']]
assert [len(groups[x]) for x in ('N','N_close','N_far')]==[16,5,11]
source={};cases={};result={'definition':{'r_G':'sum_i(Su_i/Uref)/sum_i(obs_i)','delta_r':'r_on-r_off at same seed','MAE':'mean_i(abs(Su_i/Uref-obs_i)) over 80','FAC2':'fraction_i(0.5<= (Su_i/Uref)/obs_i <=2) over 80','Uref':U},'groups':groups,'sources':source,'seeds':{}}
for seed in (101,102):
 for mode in ('off','on'):
  label=f'E_s{seed}_{mode}';p=(E if mode=='on' or seed==101 else T5)/f'{label}_points80.json'
  source[label]={'path':str(p),'sha256':verified(p)}
  if mode=='off':assert source[label]['sha256']==TARGET[label]
  cases[label]=points(p)
for seed in (101,102):
 off=cases[f'E_s{seed}_off'];on=cases[f'E_s{seed}_on']
 assert all(math.isclose(off[i]['obs'],on[i]['obs'],abs_tol=1e-12) for i in off)
 def ratio(q,ids):return sum(q[i]['Su']/U for i in ids)/sum(q[i]['obs'] for i in ids)
 def stats(q):
  errors=[q[i]['Su']/U-q[i]['obs'] for i in range(1,81)]
  return {'MAE':sum(map(abs,errors))/80,'FAC2':sum(.5<=q[i]['Su']/U/q[i]['obs']<=2 for i in range(1,81))/80}
 result['seeds'][str(seed)]={'groups':{g:{'off':ratio(off,ids),'on':ratio(on,ids),'delta_r':ratio(on,ids)-ratio(off,ids)} for g,ids in groups.items()},'wide_delta_mean_point_normalized':sum((on[i]['Su']-off[i]['Su'])/U/off[i]['obs'] for i in groups['wide'])/len(groups['wide']),'metrics80':{'off':stats(off),'on':stats(on)},'points':{str(i):{'obs':off[i]['obs'],'off_Su_over_Uref':off[i]['Su']/U,'on_Su_over_Uref':on[i]['Su']/U,'off_Su_mps':off[i]['Su'],'on_Su_mps':on[i]['Su']} for i in (50,74)}}
result['mean_delta_r_N_far']=sum(result['seeds'][str(s)]['groups']['N_far']['delta_r'] for s in (101,102))/2
v=[result['seeds'][str(s)]['groups']['N_far']['delta_r'] for s in (101,102)]
result['f_bar_thin']=json.loads((R/'coverage.json').read_text()).get('f_bar')
if result['mean_delta_r_N_far']>=.10 and all(x>=.05 for x in v):result['verdict']='立面阻力是主要杠杆（本配置、平直立面部分覆盖的界限实验）'
elif all(abs(x)<.04 for x in v):result['verdict']='中间（覆盖不足；f̄<0.6，不能判立面阻力不是主要杠杆）'
else:result['verdict']='中间'
result['physical_limit']='棱、角、屋顶、贴地第一层仍无滑移；不是立面完全无阻力。'
for label in ('E_s101_off','E_s101_on','E_s102_on'):
 for suffix in ('solver.log','fluid_mask.json','actual_opencl.cl','exit.json'):
  p=E/f'{label}_{suffix}';verified(p)
 log=(E/f'{label}_solver.log').read_text(errors='replace')
 outer=re.search(r'T9B_OUTER_FLAGS total=(\d+) TYPE_S=(\d+) TYPE_E=(\d+) bad=(\d+)',log)
 patch=re.search(r'T9B_MISSING_PATCH path=([^ ]+) patch_sampler=not_used missing_patch_samples=(\d+)',log)
 assert outer and patch and int(outer[4])==int(patch[2])==0 and 'NVIDIA A100-SXM4-40GB' in log and '| Avg samples     | 500 ' in log and '| Task finished   |' in log,label
 result['sources'][label].update({'solver_exit':json.loads((E/f'{label}_exit.json').read_text())['solver_exit'],'outer_flags':list(map(int,outer.groups())),'missing_patch_samples':int(patch[2]),'boundary_path':patch[1],'device':'NVIDIA A100-SXM4-40GB','fluid_mask_sha256':json.loads((E/f'{label}_fluid_mask.json').read_text())['mask_sha256'],'opencl_sha256':digest(E/f'{label}_actual_opencl.cl')})
 assert result['sources'][label]['solver_exit']==0
assert json.loads((E/'gate1.json').read_text())['passed'] and json.loads((E/'gate3.json').read_text())['passed']
assert result['sources']['E_s101_off']['fluid_mask_sha256']==result['sources']['E_s101_on']['fluid_mask_sha256']
assert json.loads((E/'points80_difference.json').read_text())['count']==80
assert verified(E/'run.done')
out=R/'T9b_verdict_v2.json';assert not out.exists(),out
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verdict':result['verdict'],'mean_delta_r_N_far':result['mean_delta_r_N_far'],'seeds':result['seeds'],'f_bar_thin':result['f_bar_thin']},ensure_ascii=False,indent=2))
