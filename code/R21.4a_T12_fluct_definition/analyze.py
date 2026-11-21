#!/usr/bin/env python3
"""T12 read-only input audit and strictly separated same-height exploratory comparison."""
import csv, hashlib, json, math
from pathlib import Path
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
L=R/'06_Logs'; U=3.9286416
P={
 'widths':L/'tacc_feasibility/T2c_post/widths.csv',
 't2c_points':L/'tacc_feasibility/T2c_post/out_3694005/points_all_heights.json',
 'b2u_reference':L/'tacc_feasibility/T2c_post/B2u_reference_points.json',
 'b2u_original':L/'method_study/B2u_scalar_mean/offset_samples_a_r10.json',
 'b2u_points_csv':L/'method_study/B2u_scalar_mean/points_80.csv',
 'widths_generator':L/'method_study/deadpoints_diag/analyze_deadpoints.py',
 'b2u_extractor':L/'method_study/B2u_scalar_mean/extract_B2u.py',
 't2c_postprocessor':L/'tacc_feasibility/T2c_post/post_t2c.py',
 't10b_script':L/'R21.4a_T10b_contrast/analyze.py',
 't10b_result':L/'R21.4a_T10b_contrast/T10b_result.json',
 'design':R/'04_Decisions/R21.4a_T12_脉动口径对疏密对比_设计与判据_20261118.md',
}
sha={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in P.items()}
def j(name):return json.loads(P[name].read_text())
def table(name):return {int(x['id']):x for x in csv.DictReader(P[name].open(newline=''))}
w=table('widths'); b=table('b2u_points_csv'); t={int(x['id']):x for x in j('t2c_points') if x['h_wall_m']==2.0}
ref=j('b2u_reference'); orig=j('b2u_original'); base=j('t10b_result')
assert sha['b2u_reference']==sha['b2u_original']
assert ref['vtk']=='/content/b2u_case/case_a/RESULTS/vtk/20251222120000_avg-000031000.vtk'
assert set(w)==set(b)==set(t)==set(range(1,81))
assert len(ref['rows'])==80 and set(int(x['id']) for x in ref['rows'])==set(w)
assert all(abs(float(w[i]['k_m2s2'])-float(b[i]['k']))<1e-12 for i in w)
assert all(abs(float(w[i]['Su'])-float(b[i]['Su']))<1e-12 for i in w)
assert all(abs(float(w[i]['obs_W'])-float(b[i]['obs']))<1e-12 for i in w)

assert all(abs(float(t[i]['obs'])-float(b[i]['obs']))<1e-12 for i in w)
assert all(abs(float(t[i]['baseline_1m']['xyz_m'][2])-2.5)<1e-12 for i in w)
assert all(abs(float(w[i]['S_obs'])-float(b[i]['S'])/float(b[i]['obs']))<1e-12 for i in w)
assert all(abs(float(w[i]['Sstar_obs'])-float(b[i]['Sstar'])/float(b[i]['obs']))<1e-12 for i in w)
assert all(abs(float(b[i]['k'])-float(ref['rows'][i-1]['sample']['plus_dx']['tke_m2s2']))<1e-12 for i in w)
assert all(abs(float(b[i]['Su'])-float(ref['rows'][i-1]['sample']['plus_dx']['Su_ratio']))<1e-12 for i in w)

median=base['classification']['disk50_cover_median']; dense=base['classification']['dense_ids']; sparse=base['classification']['sparse_ids']
assert len(dense)==len(sparse)==40 and set(dense)|set(sparse)==set(w)
assert all((float(w[i]['disk50_cover'])>=median)==(i in dense) for i in w)
def calc(p,obs):
 a=sum(p[i]*obs[i] for i in w)/sum(p[i]*p[i] for i in w)
 e={i:a*p[i]-obs[i] for i in w}
 d=sum(e[i] for i in dense)/len(dense); s=sum(e[i] for i in sparse)/len(sparse)
 return {'a_80':a,'mean_dense_e':d,'mean_sparse_e':s,'C':s-d}
obs={i:float(t[i]['obs']) for i in w}; su={i:float(t[i]['baseline_1m']['Su'])/U for i in w}
standard=calc(su,obs)
assert abs(standard['C']-base['configs']['off_s100']['C'])<1e-12
assert abs(standard['a_80']-base['configs']['off_s100']['a_80'])<1e-12
# The CSV k is at z=2.0 while the preregistered comparison Su is at z=2.5.
# Never mix them into a putative T12 test. A separate same-height B2u diagnostic is clearly labeled.
su_z2={i:float(b[i]['Su']) for i in w}; k_z2={i:float(b[i]['k']) for i in w}
up_z2={i:math.sqrt((su_z2[i]*U)**2+2*k_z2[i])/U for i in w}
z2_a=calc(su_z2,obs); z2_b=calc(up_z2,obs)
# These columns are MODEL/obs ratios, not alternative observed speeds. These numbers
# are arithmetic diagnostics only and must not be described as an observation test.
substitutions={key:calc(su,{i:float(w[i][key]) for i in w}) for key in ('S_obs','Sstar_obs')}
result={
 'status':'数据不足，不判', 'Uref_m_per_s':U,
 'target':{'seed':'s100 B2u/T2c 1m closed','h_wall_m':2.0,'vtk_label_z_m':2.5,
           'C_Su':standard['C'],'a_80_Su':standard['a_80'],
           'C_S_up':None,'a_80_S_up':None,'k_need_m2s2':None,'k_need_over_k_res':None,
           'verdict':'数据不足，不判','reason':'widths k at VTK label z=2.0 m, target Su at label z=2.5 m; no same-point same-height k in checked local point tables'},
 'exploratory_not_target':{'description':'B2u original label z=2.0 m Su and k, both same seed and height but NOT preregistered h_wall=2.0 (z=2.5 m) comparison; no T12 verdict',
    'C_Su':z2_a['C'],'C_S_up':z2_b['C'],'C_ratio':z2_b['C']/z2_a['C'],
    'a_80_Su':z2_a['a_80'],'a_80_S_up':z2_b['a_80'],
    'mean_dense_Su_e':z2_a['mean_dense_e'],'mean_sparse_Su_e':z2_a['mean_sparse_e'],
    'mean_dense_S_up_e':z2_b['mean_dense_e'],'mean_sparse_S_up_e':z2_b['mean_sparse_e']},
 'observation_side':{'status':'invalid as observation replacement','reason':'S_obs=S_model/obs_W and Sstar_obs=Sstar_model/obs_W, neither is an observed velocity','requested_observation_contrast':None,'arithmetic_substitution_only_not_observation':substitutions},
 'provenance':{'widths_k':'B2u original 1m closed VTK tke via trilinear point extraction at physical z=2.0m; m2/s2, then copied through deadpoints_diag to T2c_post',
   'Su_target':'same B2u VTK in T2c postprocessor, physical z=wall1(0.5)+h_wall(2.0)=2.5m',
   'S_obs':'B2u model S/obs_W, dimensionless', 'Sstar_obs':'B2u model Sstar/obs_W, dimensionless',
   'AF_caseE_csv':'upstream approaching-flow z/U/k only; does not define the widths.csv columns; readme_caseE.md describes AF as vertical profile'},
 'required_data':'B2u/T2c 1 m closed time-averaged VTK tke field sampled by identical T2c trilinear operator at x/y and z=2.5 m for all 80 points (or authenticated same-height point table); for observation-side change obtain actual experimental paired scalar/vector speed definition and measurements.',
 'input_sha256':{str(P[n]):v for n,v in sha.items()}}
(O/'T12_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('T12',result['status'],'target_C',standard['C'],'exploratory_z2_C',z2_a['C'],z2_b['C'],'hashes',len(sha))
