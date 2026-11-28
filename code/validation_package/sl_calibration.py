#!/usr/bin/env python3
"""T02 statistical linearization A/B/Q; run only on CRC compute allocation.
The input target leaves impact/re-engagement mechanics unspecified. This code uses
an explicitly labelled instantaneous gated-inertia assumption; not a physical
contact/impact model. A uses closed Gaussian moments; B uses Gauss-Hermite
quadrature (independent closure); Q puts the gap on a stiffness channel.
"""
import argparse
import json
import math
import sys
from pathlib import Path
import numpy as np
from scipy.linalg import solve_continuous_lyapunov
from scipy.optimize import minimize_scalar
from scipy.special import erfc, ndtr
from scipy.integrate import quad

TEMPLATE = Path(__file__).with_name('tmdi_powerlaw_sl.py')
import importlib.util
spec=importlib.util.spec_from_file_location('tmdi_template',TEMPLATE)
tm=importlib.util.module_from_spec(spec); spec.loader.exec_module(tm)
BASE=dict(tm.P)
CASES={'small':(.02,.01),'medium':(.10,.05),'large':(.30,.20),'X':(.10,.50)}
EB=np.array([-BASE['phi_b'],1.0]); ED=np.array([-1.0,1.0])

def matrices(nu,cd,beq,ceq,kghost=0.):
    P=BASE; ws=2*np.pi*P['f_s']; md=P['mu']*P['M']
    mass=np.diag([P['M'],md])+beq*np.outer(EB,EB)
    stiff=np.array([[P['M']*ws*ws,0.],[0.,0.]]) + (md+P['beta']*P['M'])*(nu*ws)**2*np.outer(ED,ED)+kghost*np.outer(EB,EB)
    damp=np.diag([2*P['zeta_s']*P['M']*ws+P['kappa']*P['U'],0.])+cd*np.outer(ED,ED)+ceq*np.outer(EB,EB)
    inv=np.linalg.inv(mass); af,bf,cf=tm.filter_ss(np.array(json.loads(Path(__file__).with_name('filter_params.json').read_text())))
    A=np.zeros((6,6)); A[:2,2:4]=np.eye(2)
    A[2:4,:2]=-inv@stiff; A[2:4,2:4]=-inv@damp
    A[2:4,4:6]=[邮箱]([P['kappa']*P['U'],0.])[:,None]@cf
    A[4:,4:]=af
    B=np.zeros((6,1)); B[4:,0]=bf[:,0]
    return A,B,inv,stiff,damp,cf

def moment_bounded(A,B,inv,stiff,damp,cf):
    S=solve_continuous_lyapunov(A,[邮箱])
    sx=np.zeros(6); sx[:2]=EB
    sv=np.zeros(6); sv[2:4]=EB
    aa=np.zeros(6); aa[:2]=-EB@inv@stiff; aa[2:4]=-EB@inv@damp
    aa[4:6]=float(EB@[邮箱]([BASE['kappa']*BASE['U'],0.]))*cf[0]
    sigx=np.sqrt(max(sx@S@sx,1e-30)); sigv=np.sqrt(max(sv@S@sv,1e-30))
    siga=np.sqrt(max(aa@S@aa,1e-30)); rho=np.clip(sx@S@aa/sigx/siga,-1,1)
    return S,sigx,sigv,siga,rho

def coeffs(kind,Fc,delta,sx,sv,sa,rho,b):
    t=delta/sx
    if kind in ('A','Q'):
        c=math.sqrt(2/math.pi)*Fc/sv
        prob=erfc(t/math.sqrt(2))
        gate=prob+rho*rho*math.sqrt(2/math.pi)*t*math.exp(-t*t/2)
    else:
        # Independent numeric Gaussian quadrature: sign(v)*v/sigma_v²;
        # conditional E[a²|x] = sigma_a²[(1-rho²)+rho²(x/sigma_x)²].
        phi=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
        c=Fc/sv*2*quad(lambda z:z*phi(z),0,12,epsabs=1e-12)[0]
        gate=2*quad(lambda z:((1-rho*rho)+rho*rho*z*z)*phi(z),t,12,epsabs=1e-12)[0]
    return c,b*gate

def solve(kind,Fc,delta,nu,cd,maxit=220):
    b=BASE['beta']*BASE['M']; beq=b; ceq=0.; ghost=0.; last=None
    for it in range(maxit):
        A,B,inv,K,C,cf=matrices(nu,cd,beq,ceq,ghost)
        if np.max(np.linalg.eigvals(A).real)>=0: raise ValueError('unstable equivalent system')
        S,sx,sv,sa,rho=moment_bounded(A,B,inv,K,C,cf)
        c,eff=coeffs(kind,Fc,delta,sx,sv,sa,rho,b)
        newghost=eff*(2*np.pi*BASE['f_s'])**2 if kind=='Q' else 0.
        newb=b if kind=='Q' else eff
        current=np.array([beq,ceq,ghost]); target=np.array([newb,c,newghost]); last=(S,sx,sv,sa,rho)
        if np.max(np.abs(target-current)/np.maximum(1.,np.abs(target)))<1e-9: break
        beq,ceq,ghost=.65*current+.35*target
    else: raise RuntimeError('SL fixed point did not converge')
    A,B,inv,K,C,cf=matrices(nu,cd,beq,ceq,ghost)
    S,sx,sv,sa,rho=moment_bounded(A,B,inv,K,C,cf)
    return {'sigma_q':float(np.sqrt(S[0,0])),'sigma_stroke':float(np.sqrt(S[0,0]+S[1,1]-2*S[0,1])),
            'sigma_xrel':float(sx),'sigma_vrel':float(sv),'sigma_arel':float(sa),
            'rho_xa':float(rho),'b_equiv':float(beq),'c_f_equiv':float(ceq),
            'k_wrong':float(ghost),'iterations':it+1}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); a=ap.parse_args()
    pf=tm.fit_filter(BASE['U'],BASE['I_u'],BASE['L_k'])
    nu0=.9783145940392678; cd=7276.0250356865
    A,B,*_=matrices(nu0,cd,BASE['beta']*BASE['M'],0.)
    S=solve_continuous_lyapunov(A,[邮箱])
    linx=np.sqrt(EB@S[:2,:2]@EB)
    _,_,inv,K,C,cf=matrices(nu0,cd,BASE['beta']*BASE['M'],0.)
    _,_,_,lina,_=moment_bounded(A,B,inv,K,C,cf)
    out={'model_assumption':'instantaneous gated inertial force b*a_rel*1(|x_rel|>delta); Q instead replaces b by displacement stiffness dead-zone; no contact impact specified',
         'linear_point':{'nu':nu0,'c_d':cd,'sigma_xrel':float(linx),'sigma_arel':float(lina)},'cases':{}}
    for case,(rf,rg) in CASES.items():
        Fc=rf*BASE['beta']*BASE['M']*lina; delta=rg*linx
        rows={}
        for kind in ('A','B','Q'):
            fixed=solve(kind,Fc,delta,nu0,cd)
            opt=minimize_scalar(lambda nu:solve(kind,Fc,delta,nu,cd)['sigma_q'],bounds=(.8,1.15),method='bounded',options={'xatol':1e-5})
            rows[kind]={'fixed':fixed,'nu_opt':float(opt.x),'sigma_q_opt':float(opt.fun)}
        out['cases'][case]={'r_f':rf,'r_g':rg,'F_c':float(Fc),'delta':float(delta),'methods':rows}
    Path(a.out).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'out':a.out,'cases':list(out['cases'])}))
if __name__=='__main__': main()
