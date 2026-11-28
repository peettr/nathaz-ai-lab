#!/usr/bin/env python3
"""Independent T02 closure C. Execute numerical solve on CRC only.

Gated inertance is projected with an independence approximation:
b_eq=b P(|x_b|>delta); unlike A/B no acceleration/displacement correlation.
The spring remains attached across the gap. Fixed c_d; optimize nu only.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from scipy.linalg import solve_continuous_lyapunov
from scipy.optimize import minimize_scalar
from scipy.special import erfc

ROOT=Path(__file__).resolve().parent
M=437000.; FREQ=.32; ZETA=.01; KAPPA=245.; U=30.; MU=.01; BETA=.05; PHI=.5
CD=7276.0250356865; NU0=.9783145940392678
GAP_AX=np.array([-PHI,1.]); SPR_AX=np.array([-1.,1.]); BVAL=BETA*M
CASES={'small':(.02,.01),'medium':(.10,.05),'large':(.30,.20),'X':(.10,.50)}


def system(nu, inertance, friction_damping, filter_log):
    ws=2*math.pi*FREQ
    md=MU*M
    mass=np.diag([M,md])+inertance*np.outer(GAP_AX,GAP_AX)
    invmass=np.linalg.inv(mass)
    stiffness=np.diag([M*ws**2,0.])+(md+BVAL)*(nu*ws)**2*np.outer(SPR_AX,SPR_AX)
    damping=np.diag([2*ZETA*M*ws+KAPPA*U,0.])+CD*np.outer(SPR_AX,SPR_AX)+friction_damping*np.outer(GAP_AX,GAP_AX)
    a0,a1,c0,c1=np.exp(filter_log)
    state=np.zeros((6,6));state[:2,2:4]=np.eye(2)
    state[2:4,:2]=-invmass@stiffness
    state[2:4,2:4]=-invmass@damping
    state[2:4,4:6]=np.outer([邮箱]([KAPPA*U,0.]),[c0,c1])
    state[4:6,4:6]=[[0.,1.],[-a0,-a1]]
    drive=np.zeros((6,1));drive[5,0]=1.
    return state,drive,invmass,stiffness,damping,np.array([c0,c1])


def moments(nu, inertance, friction_damping, pf):
    a,g,im,k,d,cf=system(nu,inertance,friction_damping,pf)
    if np.linalg.eigvals(a).real.max()>=0: raise ValueError('unstable linear closure')
    cov=solve_continuous_lyapunov(a,[邮箱])
    pos=np.zeros(6); pos[:2]=GAP_AX
    vel=np.zeros(6); vel[2:4]=GAP_AX
    acc=np.zeros(6);acc[:2]=-GAP_AX@im@k;acc[2:4]=-GAP_AX@im@d
    acc[4:]=float(GAP_AX@[邮箱]([KAPPA*U,0.]))*cf
    return cov,*[math.sqrt(max(float(w@cov@w),1e-30)) for w in (pos,vel,acc)]


def fixed_point(nu, fc, gap, pf):
    inertance=BVAL; friction=0.
    for iteration in range(500):
        cov,sx,sv,_=moments(nu,inertance,friction,pf)
        # C: marginal displacement gate, no E[a^2|x] correction.
        wanted_b=BVAL*erfc(gap/(math.sqrt(2)*sx))
        wanted_c=math.sqrt(2/math.pi)*fc/sv
        old=np.array([inertance,friction]); target=np.array([wanted_b,wanted_c])
        if np.max(np.abs(target-old)/np.maximum(1.,np.abs(target)))<1e-9: break
        inertance,friction=.65*old+.35*target
    else: raise RuntimeError('C fixed point not converged')
    cov,sx,sv,sa=moments(nu,inertance,friction,pf)
    return {'sigma_q':math.sqrt(cov[0,0]),'sigma_stroke':math.sqrt(cov[0,0]+cov[1,1]-2*cov[0,1]),
            'sigma_xrel':sx,'sigma_vrel':sv,'sigma_arel':sa,'b_equiv':inertance,
            'c_f_equiv':friction,'iterations':iteration+1}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    pf=np.array(json.loads((ROOT/'filter_params.json').read_text()))
    _,sx0,_,sa0=moments(NU0,BVAL,0.,pf)
    # Freeze exactly the same physical F_c and delta as A/B/Q and the MC.
    # Read their serialized INPUT values, not their solver or closure code.
    frozen=json.loads((ROOT/'sl_results.json').read_text())['cases']
    records={}
    for case,(rf,rg) in CASES.items():
        assert frozen[case]['r_f']==rf and frozen[case]['r_g']==rg
        fc=float(frozen[case]['F_c']); gap=float(frozen[case]['delta'])
        fixed=fixed_point(NU0,fc,gap,pf)
        opt=minimize_scalar(lambda nu:fixed_point(nu,fc,gap,pf)['sigma_q'],
                            bounds=(.8,1.15),method='bounded',options={'xatol':1e-5})
        if not opt.success: raise RuntimeError(f'{case}: optimizer failed: {opt.message}')
        records[case]={'r_f':rf,'r_g':rg,'F_c':fc,'delta':gap,'fixed':fixed,
                       'nu_opt':float(opt.x),'sigma_q_opt':float(opt.fun)}
    result={'method':'C: independent-displacement-gate b*P(|x_b|>delta), Coulomb Gaussian energy projection',
            'linear_point':{'nu':NU0,'c_d':CD,'sigma_xrel':sx0,'sigma_arel':sa0},'cases':records}
    Path(args.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cases':list(records),'out':args.out}))

if __name__=='__main__':main()
