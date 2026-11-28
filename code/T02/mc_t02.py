#!/usr/bin/env python3
"""CRC-only MC under the explicit gated-inertia assumption in sl_calibration.py.
Structure RK4 with piecewise inertance; exact OU filter stepping, linear
interpolation of u over step. Gap crossing is refined by dt-halving test,
not an impulsive contact law (none was specified). Independent trajectories.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from scipy.linalg import expm, solve_continuous_lyapunov
import sl_calibration as sl
P=sl.BASE; EB=sl.EB; ED=sl.ED

def run(case, nu, *, n=200, dt=.01, T=1800., burn=300., seed=20261127,v0=0.):
    rf,rg=sl.CASES[case]; cd=7276.0250356865
    A,B,inv,K,C,cf=sl.matrices(.9783145940392678,cd,P['beta']*P['M'],0.)
    S=solve_continuous_lyapunov(A,[邮箱])
    sigx=math.sqrt(EB@S[:2,:2]@EB)
    aa=np.zeros(6); aa[:2]=-EB@inv@K; aa[2:4]=-EB@inv@C
    aa[4:]=float(EB@[邮箱]([P['kappa']*P['U'],0.]))*cf[0]
    siga=math.sqrt(aa@S@aa)
    Fc=rf*P['beta']*P['M']*siga; gap=rg*sigx
    ws=2*math.pi*P['f_s']; md=P['mu']*P['M']; b=P['beta']*P['M']
    K=np.array([[P['M']*ws**2,0.],[0.,0.]])+(md+b)*(nu*ws)**2*np.outer(ED,ED)
    C=np.diag([2*P['zeta_s']*P['M']*ws+P['kappa']*P['U'],0.])+cd*np.outer(ED,ED)
    Minv0=np.diag([1/P['M'],1/md]); uvec=Minv0@EB
    den=1+b*(EB@uvec)
    af,bf,cf=sl.tm.filter_ss(np.array(json.loads(Path(__file__).with_name('filter_params.json').read_text())))
    z=np.zeros((4,4)); z[:2,:2]=-af; z[:2,2:]=[邮箱]; z[2:,2:]=af.T
    ez=expm(z*dt); phi=ez[2:,2:].T; qd=phi@ez[:2,2:]; chol=np.linalg.cholesky((qd+qd.T)/2)
    rng=np.random.default_rng(seed)
    # Stable stationary initial distribution for the *linear* reference.
    init=rng.multivariate_normal(np.zeros(6),S,size=n).T
    x=init[:2].copy(); v=init[2:4].copy(); filt=init[4:].copy(); u=(cf@filt)[0]
    force=np.array([P['kappa']*P['U'],0.])[:,None]
    def acc(xx,vv,uu):
        vr=EB@vv
        friction=Fc*(np.sign(vr) if not v0 else np.tanh(vr/v0))
        rhs=force*uu-C@vv-K@xx-EB[:,None]*friction
        bare=Minv0@rhs
        active=np.abs(EB@xx)>gap
        return bare-uvec[:,None]*(b/den)*(EB@bare)[None,:]*active[None,:]
    nb=int(round(burn/dt)); nt=int(round(T/dt))
    sq=np.zeros(n); ss=np.zeros(n)
    for k in range(nb+nt):
        f1=phi@[邮箱]((2,n)); u1=(cf@f1)[0]; um=(u+u1)/2
        a1=acc(x,v,u)
        v2=v+.5*dt*a1; a2=acc(x+.5*dt*v,v2,um)
        v3=v+.5*dt*a2; a3=acc(x+.5*dt*v2,v3,um)
        v4=v+dt*a3; a4=acc(x+dt*v3,v4,u1)
        x=x+dt/6*(v+2*v2+2*v3+v4)
        v=v+dt/6*(a1+2*a2+2*a3+a4)
        filt=f1; u=u1
        if k>=nb: sq+=x[0]*x[0]; ss+=(x[1]-x[0])**2
    sq/=nt; ss/=nt
    # Parametric bootstrap of independent trajectory averages; time autocorrelation
    # remains within each trajectory; deterministic independent bootstrap seed.
    rboot=np.random.default_rng(seed+3127)
    ix=rboot.integers(n,size=(1500,n))
    bsq=np.sqrt(sq[ix].mean(axis=1)); bss=np.sqrt(ss[ix].mean(axis=1))
    return {'case':case,'nu':nu,'c_d':cd,'F_c':Fc,'delta':gap,'n_traj':n,'T_s':T,'burn_s':burn,'dt_s':dt,'v0_mps':v0,
            'sigma_q':float(np.sqrt(sq.mean())),'sigma_stroke':float(np.sqrt(ss.mean())),
            'ci95_sigma_q':np.quantile(bsq,[.025,.975]).tolist(),'ci95_sigma_stroke':np.quantile(bss,[.025,.975]).tolist(),
            'trajectory_sigma_q_sd':float(np.std(sq,ddof=1)),'seed':seed}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('case',choices=sl.CASES); ap.add_argument('--nu',type=float,default=.9783145940392678)
    ap.add_argument('--n',type=int,default=200); ap.add_argument('--dt',type=float,default=.01); ap.add_argument('--T',type=float,default=1800.)
    ap.add_argument('--burn',type=float,default=300.); ap.add_argument('--v0',type=float,default=0.)
    ap.add_argument('--seed',type=int,default=20261127); ap.add_argument('--out',required=True)
    a=ap.parse_args(); out=run(a.case,a.nu,n=a.n,dt=a.dt,T=a.T,burn=a.burn,seed=a.seed,v0=a.v0)
    Path(a.out).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n'); print(json.dumps({'out':a.out,'sigma_q':out['sigma_q']}))
if __name__=='__main__': main()
