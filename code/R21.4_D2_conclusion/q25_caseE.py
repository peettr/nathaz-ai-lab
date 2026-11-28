#!/usr/bin/env python3
"""q25 for Case E configs. q25 = #{|p-o|/o <= 0.25}/80, p=Su/Uref. Loaders reused from T10a analyze.py (read-only)."""
import sys,json,hashlib,importlib.util
R='./24_Urban_Wind_LBM/06_Logs/'
spec=importlib.util.spec_from_file_location('an',R+'R21.4a_T10a_error_structure/analyze.py');an=importlib.util.module_from_spec(spec);spec.loader.exec_module(an)
U=an.U
cfg={'off_s100':an.from_t2c('baseline_1m'),'off_s103':an.from_t2d()}
cfg['fine_0p5_s100']={int(r['id']):(float(r['fine']['primary']['Su'])/U,float(r['obs'])) for r in an.read(an.T2) if r['h_wall_m']==2.0}
inputs=[str(an.T2)]
for seed in (101,102):
    for label,base,state in [('off',an.T5,'off'),('T5_on',an.T5,'on'),('T6_on',an.T6,'on'),('T7',an.T7,'off'),('T9b_on',an.T9,'on')]:
        p=base/f'E_s{seed}_{state}_points80.json'; cfg[f'{label}_s{seed}']=an.rows_points(p); inputs.append(str(p))
    p=R+f'R21.4a_T13_smag_cs010/T13b_20261118_104520/run_luw-t13b-a100-b309d362/evidence/E_s{seed}_off_points80.json'
    cfg[f'T13b_cs013_s{seed}']=an.rows_points(__import__('pathlib').Path(p)); inputs.append(p)
out={}
for k,d in cfg.items():
    n=sum(abs(p-o)/o<=0.25 for p,o in d.values())
    out[k]={'hits':n,'n':len(d),'q25':n/len(d),'MAE':sum(abs(p-o) for p,o in d.values())/len(d)}
sha={p:hashlib.sha256(open(p,'rb').read()).hexdigest() for p in inputs}
json.dump({'definition':'q25 = #{|p-o|/o <= 0.25}/80; p=Su/Uref, Uref=3.9286416; 0.66 threshold = 53/80 points','script':sys.argv[0],'results':out,'input_sha256':sha},open(R+'R21.4_D2_conclusion/q25_caseE_v2.json','w'),ensure_ascii=False,indent=1)
for k,v in out.items(): print(f"{k:18s} {v['hits']}/80 = {v['q25']:.4f}  MAE {v['MAE']:.4f}")
