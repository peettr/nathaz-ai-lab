#!/usr/bin/env python3
"""T18 v2 decision §§2–4, decision lines 35–90. No physics is inferred from fixtures."""
import argparse, importlib.util, json, math
from pathlib import Path
T17 = Path('./24_Urban_Wind_LBM/06_Logs/R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455/assert_T17.py')
spec=importlib.util.spec_from_file_location('frozen_t17',T17)
t17=importlib.util.module_from_spec(spec);spec.loader.exec_module(t17)
ORDER=('K1a','K1b','K2','K3a','K3b')
RPAT=0.0024082619336659172

def finite(v):
    v=float(v)
    if not math.isfinite(v): raise ValueError('nonfinite metric')
    return v

def metrics(case):
    # §2 lines 35–41 and §3 lines 49–52: import frozen metric implementation.
    return t17.seed_metrics(case)

def eligible(m):
    return m['valid'] and abs(m['S2']['e_2p5'])<=.10 and m['S2b']['rmse']<=.10

def calibrate(cases):
    # §2 lines 37–42: eligibility, empty, failure, 0.015 tie, fixed minimal-change order.
    m={k:metrics(v) for k,v in cases.items()}
    eligible_names=[k for k in ORDER if k in m and eligible(m[k])]
    if not eligible_names: return {'status':'标定集不判','selected':None,'metrics':m}
    minimum=min(m[k]['S3']['max_abs_difference'] for k in eligible_names)
    if minimum>.30: return {'status':'标定失败','selected':None,'S3_min':minimum,'metrics':m}
    possible=[k for k in eligible_names if m[k]['S3']['max_abs_difference']<=.30 and m[k]['S3']['max_abs_difference']<=minimum+.015]
    if not possible: raise AssertionError('no selectable minimum')
    return {'status':'选定','selected':possible[0],'S3_min':minimum,'tie_candidates':possible,'metrics':m}

def abl(case):
    # §3 lines 49–52: one seed; invalid dominates, then all three scientific gates.
    m=metrics(case)
    verdict='不判' if not m['valid'] else ('达标' if eligible(m) and m['S3']['max_abs_difference']<=.30 else '未达标')
    return {'verdict':verdict,'metrics':m}

def ve(rows):
    # §4 lines 67–77: paired seeds, MAE differences and no-wall guard.
    if rows is None or set(rows)!= {'s101','s102'}:return {'verdict':'缺测','available_seeds':list(rows or {})}
    if any(not rows[s].get('stable',False) for s in rows): return {'verdict':'失稳','stability':rows}
    delta={s:finite(rows[s]['cal']['mae'])-finite(rows[s]['uncal']['mae']) for s in rows}
    vals=list(delta.values())
    if all(x<=-.01+1e-12 for x in vals): verdict='改善'
    elif all(x>=+.01-1e-12 for x in vals): verdict='变差'
    elif all(abs(x)<.01-1e-12 for x in vals): verdict='在种子变化内'
    else: verdict='不一致'
    guard={s:finite(rows[s]['cal']['mae'])<=finite(rows[s]['baseline']['mae'])+.01 for s in rows}
    details={}
    for s,r in rows.items():
        pat=finite(r['cal']['mse_pat'])-finite(r['uncal']['mse_pat'])
        details[s]={'delta_MAE':delta[s],'delta_MSE_pat':pat,'pattern':'格局变差' if pat>RPAT else '格局改善' if pat< -RPAT else '格局不变','delta_C':finite(r['cal']['C'])-finite(r['uncal']['C']),'guard_pass':guard[s]}
    return {'verdict':verdict,'guard_pass':all(guard.values()),'per_seed':details}

def vp(rows):
    # §4 lines 78–82: descriptive only; observed |Cp|>=0.1 denominator for FAC2.
    if rows is None:return {'status':'缺测','note':'风压只作描述，没有通过线'}
    out={}
    for name,r in rows.items():
        vals={}
        for quantity in ('mean','rms','negative_peak','positive_peak'):
            obs=[finite(x) for x in r['obs'][quantity]]
            v=[finite(x) for x in r['model'][quantity]]
            if len(obs)!=len(v) or not obs:raise ValueError('V-P point alignment')
            mae=sum(abs(a-b) for a,b in zip(obs,v))/len(obs)
            q={'mae':mae}
            if quantity in ('mean','rms'):
                idx=[i for i,x in enumerate(obs) if abs(x)>=.1]
                q['FAC2']=sum(.5<=v[i]/obs[i]<=2 for i in idx)/len(idx) if idx else None
                q['FAC2_denominator']=len(idx)
            vals[quantity]=q
        out[name]=vals
    if 'cal' in out and 'uncal' in out:
        for quantity in ('mean','rms','negative_peak','positive_peak'):
            old=out['uncal'][quantity]['mae'];out['cal'][quantity]['relative_MAE_change']=(out['cal'][quantity]['mae']-old)/old if old else None
    return {'status':'描述','models':out,'note':'风压只作描述，没有通过线'}

def evaluate(data):
    cal=calibrate(data['calibration'])
    if cal['selected'] is None: va=None; er={'verdict':'缺测'}
    else:
        va=abl(data['validation_ABL']) if data.get('validation_ABL') is not None else {'verdict':'不判','reason':'V-ABL missing'}
        er=ve(data.get('validation_E'))
    # §4 lines 83–89: apply first true branch in written order.
    if cal['status']=='标定集不判' or (va and va['verdict']=='不判') or er['verdict']=='缺测' and cal['status']!='标定失败': total='不判'
    elif cal['status']=='标定失败':total='标定失败'
    elif va['verdict']=='未达标' or er['verdict'] in ('失稳','变差') or not er.get('guard_pass',True):total='不能用'
    elif va['verdict']=='达标' and er['verdict'] in ('改善','在种子变化内'):total='能用（限 T17 平台、AIJ Case E 1 m、80 点风速 MAE）'
    else:total='部分'
    return {'calibration':cal,'V_ABL':va,'V_E':er,'V_P':vp(data.get('validation_P')),'total_verdict':total,'R_pat':RPAT}

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=evaluate(json.loads(a.input.read_text()));a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'calibration':result['calibration']['status'],'selected':result['calibration']['selected'],'total_verdict':result['total_verdict']},ensure_ascii=False))
if __name__=='__main__':main()
