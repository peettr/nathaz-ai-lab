#!/usr/bin/env python3
"""T17 B frozen §3 (decision lines 27–62). Input schema in DATA_CONTRACT.md.
Synthetic fixture inputs are pipeline-only, never scientific evidence.
"""
import argparse
import itertools
import json
import math
from pathlib import Path

H, USTAR, Z0, KAPPA, FORCE = 64.0, .27810, .024, .4, 1.20843e-3
GROUPS = ('bounce', 't4', 't15')
SEEDS = ('1', '2')

def finite(x):
    v = float(x)
    if not math.isfinite(v):
        raise ValueError('nonfinite input')
    return v

def elog(z, u):
    return finite(u)/(USTAR/KAPPA*math.log((z+Z0)/Z0))-1

def spread(a, b):
    a, b = finite(a), finite(b)
    if abs(a+b) < 1e-15:
        return 0.0 if a == b else math.inf
    return abs(b-a)/abs((a+b)/2)

def seed_metrics(data):
    # V0, lines 34–35: last 1T in two T/2 windows; allow at most 3 appended T.
    histories = data['v0_attempts']
    if not 1 <= len(histories) <= 4:
        raise ValueError('V0 requires 1..4 attempts')
    v0rows=[]
    for attempt in histories:
        if len(attempt) != 2: raise ValueError('V0 attempt needs two half-T windows')
        changes={field:spread(attempt[0][field],attempt[1][field]) for field in ('momentum','tau_x','ustar')}
        v0rows.append({'relative_changes':changes,'pass':all(v<=.02 for v in changes.values())})
    if len(v0rows)>1 and any(x['pass'] for x in v0rows[:-1]):
        raise ValueError('V0 continued after passing equilibrium')
    if len(v0rows)<4 and not v0rows[-1]['pass']:
        raise ValueError('V0 stopped before 3 permitted extensions; supply continuation or mark incomplete')
    # V1/S1, line 36: kinematic stress divided by F H. Do not multiply by rho again.
    # §3 line 36: positive tau_x is ground drag opposing +x flow (A7 sign).
    tau_x=finite(data['stress']['tau_x_time_mean'])
    rho=finite(data['stress']['rho'])
    if rho<=0: raise ValueError('nonpositive density')
    stress_ratio=tau_x/rho/(FORCE*H)
    v1=tau_x>0 and .95 <= stress_ratio <= 1.05
    # V2, line 37: block-resolved TKE about each block's horizontal-time mean.
    blocks=data['blocks'];
    if len(blocks)!=4: raise ValueError('2T statistics require four T/2 blocks')
    kvals=[finite(b['k_res_z9p5'])/USTAR**2 for b in blocks]
    if min(kvals)<0:raise ValueError('negative TKE')
    uxmeans=[finite(b['u_x_mean_z9p5']) for b in blocks]
    uxvars=[finite(b['u_x_variance_z9p5']) for b in blocks]
    if min(uxvars)<0 or any(abs(x)<1e-15 for x in uxmeans):raise ValueError('Iu undefined')
    iu=[math.sqrt(var)/abs(mean) for mean,var in zip(uxmeans,uxvars)]
    v2=all(v>=.5 for v in kvals) and min(kvals)/max(kvals)>=.8
    # V3, line 38: normalized correlations at half-domain lags, both axes.
    corr={name:finite(data['correlations'][name]) for name in ('rx_half','ry_half')}
    v3=all(abs(v)<=.1 for v in corr.values())
    # U(z_k) is signed ux, horizontal and temporal mean; k=1..64, z=k-.5 (lines 29–31).
    profile=data['profile_u'];
    if set(profile)!=set(str(k) for k in range(1,65)):
        raise ValueError('profile requires each fluid k=1..64 once')
    u={k:finite(profile[str(k)]) for k in range(1,65)}
    errors={k:elog(k-.5,u[k]) for k in range(1,65)}
    # S2, line 41: 2.5 m is k3; 2.0 m is linear midpoint of k2/k3, descriptive only.
    s2=abs(errors[3])<=.10
    u2=(u[2]+u[3])/2
    # S2b, line 42: k3..k10 inclusive (eight centers, 2.5..9.5 m).
    rmse=math.sqrt(sum(errors[k]**2 for k in range(3,11))/8)
    s2b=rmse<=.10
    # S3, line 43: staggered midpoint z=3..9, U[k+1]-U[k] at 1m separation.
    slopes={str(z):KAPPA*z/USTAR*(u[z+1]-u[z])-z/(z+Z0) for z in range(3,10)}
    slope_max=max(abs(v) for v in slopes.values());s3=slope_max<=.3
    block_errors=[elog(2.5,b['u_k3']) for b in blocks]
    reasons=[]
    if not v0rows[-1]['pass']:reasons.append('未平衡')
    if not v1:reasons.append('S1/V1应力不一致')
    if not v2:reasons.append('湍流未维持')
    if not v3:reasons.append('域长不足')
    valid=not reasons
    return {'V0':{'attempts':v0rows,'pass':v0rows[-1]['pass']},
            'V1_S1':{'ratio':stress_ratio,'pass':v1},
            'V2':{'k_over_ustar2':kvals,'min_over_max':min(kvals)/max(kvals),'Iu_by_block':iu,'pass':v2},
            'V3':{'correlations':corr,'pass':v3},
            'S2':{'e_2p5':errors[3],'pass':s2,'u_2p0_interpolated':u2,'e_2p0_descriptive':elog(2,u2)},
            'S2b':{'rmse':rmse,'pass':s2b},
            'S3':{'max_abs_difference':slope_max,'differences_by_z':slopes,
                  'sqrt_1_minus_z_over_H':{str(z):math.sqrt(1-z/H) for z in range(3,10)},'pass':s3},
            'block_e_2p5':block_errors,'invalid_reasons':reasons,'valid':valid}

def evaluate(data):
    if data.get('schema')!='T17-B-v1':raise ValueError('wrong schema')
    if set(data['cases'])!=set(GROUPS):raise ValueError('groups mismatch')
    cases={g:{} for g in GROUPS};verdict={}
    for g in GROUPS:
        if set(data['cases'][g])!=set(SEEDS):raise ValueError('two paired seeds required')
        for s in SEEDS: cases[g][s]=seed_metrics(data['cases'][g][s])
        # Lines 45–50: invalid dominates, then both seeds meet all S tests, else fail.
        if any(not cases[g][s]['valid'] for s in SEEDS):verdict[g]='不判'
        elif all(all(cases[g][s][k]['pass'] for k in ('S2','S2b','S3')) for s in SEEDS):verdict[g]='达标'
        else:verdict[g]='未达标'
    pairs={}
    for a,b in itertools.combinations(GROUPS,2):
        key=a+'__'+b
        if '不判' in (verdict[a],verdict[b]):
            pairs[key]={'verdict':'不判','reason':'invalid group'};continue
        ea=[cases[a][s]['S2']['e_2p5'] for s in SEEDS];eb=[cases[b][s]['S2']['e_2p5'] for s in SEEDS]
        ds=[x-y for x,y in zip(ea,eb)];D=sum(ds)/2
        # Lines 52–56: two seed ranges plus four individual block ranges = six terms.
        noise={'seed_range_'+a:max(ea)-min(ea),'seed_range_'+b:max(eb)-min(eb)}
        for g in (a,b):
            for s in SEEDS:
                block=cases[g][s]['block_e_2p5'];noise[f'block_range_{g}_{s}']=max(block)-min(block)
        N=max(noise.values());yes=abs(D)>2*N and abs(D)>=.02 and ds[0]*ds[1]>0
        pairs[key]={'D':D,'D_by_seed':dict(zip(SEEDS,ds)),'noise_six':noise,'N':N,
                    'abs_D_gt_2N':abs(D)>2*N,'abs_D_ge_0p02':abs(D)>=.02,
                    'same_sign':ds[0]*ds[1]>0,'S2b_rmse_difference_descriptive':sum(cases[a][s]['S2b']['rmse']-cases[b][s]['S2b']['rmse'] for s in SEEDS)/2,
                    'verdict':'可辨' if yes else '在本指标下未检出差异'}
    # Lines 58–62: T15 target met and either T4 failed/invalid or distinguishable and closer.
    link=False
    if verdict['t15']=='达标':
        pair=pairs['t4__t15']
        e15=sum(cases['t15'][s]['S2']['e_2p5'] for s in SEEDS)/2
        e4=sum(cases['t4'][s]['S2']['e_2p5'] for s in SEEDS)/2
        link=verdict['t4'] in ('未达标','不判') or (pair['verdict']=='可辨' and abs(e15)<abs(e4))
    if verdict['t15']==verdict['t4']=='达标' and pairs['t4__t15']['verdict']!='可辨':
        link_status='待Lead另写理由并rc-review count 3'
    else:link_status='符合另立Case E前置条件（仍须先写判据）' if link else '不符合另立Case E前置条件'
    return {'schema':'T17-B-result-v1','cases':cases,'group_verdicts':verdict,'pairwise':pairs,'case_E_link':link_status,
            'scope':'本周期盒、z0=0.024m目标对数律；不是Case E精度结论'}

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=evaluate(json.loads(a.input.read_text()))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'group_verdicts':result['group_verdicts'],'pairwise':{k:v['verdict'] for k,v in result['pairwise'].items()},'case_E_link':result['case_E_link']},ensure_ascii=False))
if __name__=='__main__':main()
