#!/usr/bin/env python3
"""T11 frozen criteria, verified output only; no science claim from fixture."""
import csv,hashlib,json,math,pathlib
R=pathlib.Path(__file__).resolve().parent;LOG=R.parents[1];U=3.9286416
BASE={101:'6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279',102:'b284b8075072e0c162773096c4b7ba1547f0dc41517b461058803d16d82b8bcf'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verified(p):
 assert p.is_file() and p.with_name(p.name+'.sha256').read_text().strip()==sha(p),p
 return sha(p)
def rows(p):
 q=json.loads(p.read_text());d={int(x['id']):x for x in q['rows']};assert q['uref']==U and len(d)==80 and set(d)==set(range(1,81))
 return d
def metric(d,dense,sparse,wide,far):
 p={i:d[i]['Su']/U for i in d};obs={i:d[i]['obs'] for i in d};a=sum(p[i]*obs[i] for i in p)/sum(v*v for v in p.values())
 e={i:a*p[i]-obs[i] for i in p};md=sum(e[i] for i in dense)/len(dense);ms=sum(e[i] for i in sparse)/len(sparse)
 def ratio(ids):return sum(p[i] for i in ids)/sum(obs[i] for i in ids)
 return dict(a_80=a,mean_dense_e=md,mean_sparse_e=ms,C=ms-md,MSE_pat_80=sum(v*v for v in e.values())/80,MAE_80=sum(abs(p[i]-obs[i]) for i in p)/80,wide_ratio=ratio(wide),N_far_ratio=ratio(far))
def main():
 run=sorted(R.glob('run_luw-t11-a100-*/evidence'))
 assert len(run)==1,'exactly one verified production session required'
 ev=run[0];verified(ev/'run.done');assert json.loads((ev/'run.done').read_text())==dict(verified_cases=['E_s101_off','E_s102_off'],mode='production')
 cl=json.loads((LOG/'R21.4a_T10b_contrast/T10b_result.json').read_text())['classification'];dense=cl['dense_ids'];sparse=cl['sparse_ids'];assert len(dense)==len(sparse)==40
 wid={int(x['id']):x for x in csv.DictReader((LOG/'tacc_feasibility/T2c_post/widths.csv').open())};wide=[i for i in wid if float(wid[i]['width_min_m'])>=15];far=[31,39,40,47,48,49,65,66,69,77,79];assert len(wide)==64
 seeds={};ops=[];hashes={}
 for seed in (101,102):
  label=f'E_s{seed}_off';p=ev/(label+'_points80.json');hashes[str(p)]=verified(p)
  q=ev/(label+'_upstream_slice.npz');hashes[str(q)]=verified(q)
  profile=ev/(label+'_profile.json');hashes[str(profile)]=verified(profile)
  for suffix in ('solver.log','actual_opencl.cl','exit.json'):
   path=ev/(label+'_'+suffix);hashes[str(path)]=verified(path)
  text=(ev/(label+'_solver.log')).read_text(errors='replace')
  assert 'NVIDIA A100-SXM4-40GB' in text and '| Avg samples     | 500 ' in text and '| Task finished   |' in text
  assert json.loads((ev/(label+'_exit.json')).read_text())['solver_exit']==0
  baseline=LOG/f'R21.4a_T5_caseE_WM_retry2/evidence/{label}_points80.json';assert sha(baseline)==BASE[seed];off=rows(baseline);on=rows(p)
  assert all(abs(on[i]['obs']-off[i]['obs'])<1e-12 for i in on)
  a=metric(off,dense,sparse,wide,far);b=metric(on,dense,sparse,wide,far)
  prof=json.loads(profile.read_text())['profile'];assert len(prof)==18
  gate={str(z):next(x['kappa'] for x in prof if x['x_m']==45 and x['height_agl_m']==z) for z in (10.,15.9)};ops.extend(gate.values())
  seeds[str(seed)]=dict(baseline=a,boost=b,delta_C=b['C']-a['C'],delta_MSE_pat_80=b['MSE_pat_80']-a['MSE_pat_80'],operation_x45=gate,profile=prof,baseline_sha256=BASE[seed])
 delta=[seeds[str(i)]['delta_C'] for i in (101,102)];operation=all(.85<=x<=1.25 for x in ops)
 verdict=('操作未达，不判' if not operation else '来流湍流是疏密对比的杠杆' if sum(delta)/2<=-.04 and all(x<=-.02 for x in delta) else '来流湍流不是杠杆' if all(abs(x)<.016 for x in delta) else '中间')
 result=dict(design=str(LOG.parent/'04_Decisions/R21.4a_T11_来流湍流增强对疏密对比_设计与判据_20261117.md'),operation_passed=operation,mean_delta_C=sum(delta)/2,verdict=verdict,R_pat=json.loads((LOG/'R21.4a_T10a_error_structure/T10a_result.json').read_text())['R_pat'],seeds=seeds,sha256=hashes,definition='p=Su/Uref; a80=sum(p obs)/sum(p²); e=a80*p-obs; C=mean_sparse(e)-mean_dense(e)')
 out=R/'T11_verdict.json';assert not out.exists(),out;out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'operation':operation,'mean_delta_C':result['mean_delta_C'],'verdict':verdict,'seeds':{k:{'delta_C':v['delta_C'],'gate':v['operation_x45']} for k,v in seeds.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
