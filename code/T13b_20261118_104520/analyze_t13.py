#!/usr/bin/env python3.10
"""T13 reducer: require verified real A100 point tables and stability traces."""
import csv,hashlib,json,math,pathlib,re
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[2]
T5=ROOT/'06_Logs/R21.4a_T5_caseE_WM_retry2/evidence';T10=ROOT/'06_Logs/R21.4a_T10b_contrast/T10b_result.json';W=ROOT/'06_Logs/tacc_feasibility/T2c_post/widths.csv';U=3.9286416
FROZEN={101:'6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279',102:'b284b8075072e0c162773096c4b7ba1547f0dc41517b461058803d16d82b8bcf'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(p):
 assert p.stat().st_size>0 and sha(p)==p.with_name(p.name+'.sha256').read_text().strip(),p
 return p
def points(p):
 rows={int(x['id']):x for x in json.loads(p.read_text())['rows']};assert set(rows)==set(range(1,81))
 return rows
def main():
 roots=[p for p in R.glob('run_luw-t13b-a100-*/evidence') if (p/'run.done').is_file()];assert len(roots)==1,roots
 E=roots[0];done=json.loads(verify(E/'run.done').read_text());assert done=={'mode':'production','verified_cases':['E_s101_off','E_s102_off']},done
 widths={int(x['id']):x for x in csv.DictReader(W.open(encoding='utf-8-sig'))};t10=json.loads(T10.read_text());dense=set(t10['classification']['dense_ids']);sparse=set(t10['classification']['sparse_ids']);assert len(dense)==len(sparse)==40
 wide={i for i,x in widths.items() if float(x['width_min_m'])>=15};far={31,39,40,47,48,49,65,66,69,77,79};close={50,51,52,55,74}
 sources={str(W):sha(W),str(T10):sha(T10)};cases={};ds=[]
 def metrics(rows,exclude=frozenset()):
  ids=set(rows)-set(exclude);p={i:rows[i]['Su']/U for i in ids};o={i:rows[i]['obs'] for i in ids};a=sum(p[i]*o[i] for i in ids)/sum(p[i]**2 for i in ids);e={i:a*p[i]-o[i] for i in ids}
  def ratio(g):
   selected=g&ids
   return sum(p[i] for i in selected)/sum(o[i] for i in selected) if selected else None
  return {'a_80' if not exclude else 'a_excluding_N_close':a,'C':sum(e[i] for i in sparse&ids)/len(sparse&ids)-sum(e[i] for i in dense&ids)/len(dense&ids),'MSE_pat':sum(v*v for v in e.values())/len(ids),'MAE':sum(abs(p[i]-o[i]) for i in ids)/len(ids),'r_wide':ratio(wide),'r_N_far':ratio(far),'r_N_close':ratio(close)}
 stable=True
 for seed in (101,102):
  label=f'E_s{seed}_off';b=T5/(label+'_points80.json');assert sha(b)==FROZEN[seed]
  p=verify(E/(label+'_points80.json'));log=verify(E/(label+'_solver.log'));monitor=verify(E/(label+'_city_stability.csv'));exit_=verify(E/(label+'_exit.json'))
  txt=log.read_text(errors='replace');assert 'NVIDIA A100-SXM4-40GB' in txt and json.loads(exit_.read_text())['solver_exit']==0
  mon=list(csv.DictReader(monitor.open()));assert mon and int(mon[-1]['step'])==31000
  gate=not (re.search(r'(?i)\bnan\b',txt) or 'CITY_FIRST_NONFINITE' in txt or any(x['first_nonfinite_xyz_component'].strip() for x in mon))
  on=points(p);off=points(b);assert all(on[i]['obs']==off[i]['obs'] and math.isfinite(on[i]['Su']) for i in on)
  stable &= gate;m=metrics(on);baseline=metrics(off);assert abs(baseline['C']-t10['configs'][f'off_s{seed}']['C'])<1e-12
  d=m['C']-baseline['C'];ds.append(d)
  cases[str(seed)]={'stable':gate,'monitor_rows':len(mon),'on':m,'off':baseline,'delta_C':d,'delta_MSE_pat':m['MSE_pat']-baseline['MSE_pat'],'C_excluding_N_close_on':metrics(on,close)['C'],'C_excluding_N_close_off':metrics(off,close)['C'],'points_sha256':sha(p),'solver_log_sha256':sha(log),'stability_sha256':sha(monitor),'stability_extrema_series':[{k:x.get(k) for k in ('step','max_u_lattice','min_rho','max_rho','first_nonfinite_xyz_component')} for x in mon]}
  sources.update({str(q):sha(q) for q in (b,p,log,monitor,exit_)})
 verdict='失稳，不判' if not stable else 'Cs 是疏密对比的杠杆' if sum(ds)/2<=-.04 and all(d<=-.02 for d in ds) else 'Cs 不是杠杆' if all(abs(d)<.016 for d in ds) else '中间'
 out={'definition':{'Uref':U,'a':'sum(p obs)/sum(p²)','p':'Su/Uref','e':'a*p-obs','C':'mean_sparse(e)-mean_dense(e)','R_pat':.0024},'cases':cases,'mean_delta_C':sum(ds)/2,'stability_pass':stable,'verdict':verdict,'input_sha256':sources}
 dest=R/'T13b_verdict.json';assert not dest.exists();dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(verdict,sum(ds)/2)
if __name__=='__main__':main()
