"""L22.6 T01 §5 盲区变体离参考解多远（11-05，回应审查 66c5a7bb）。不计分。
复用 sessions/claude/T01_N_r1/cand_R1/curves.py 的矩阵；只改一处做变体：
  ca10/ca30：c_a 冻结在 κ·10 或 κ·30，其余随 U(t)；P00：P(0)=0。
定义：d = √(Σ(v_var−v_base)²/Σv_base²)，e_L2 = √(Σ(v−s)²/Σs²)，s 为 MC；t=0..600 s。
"""
import importlib.util,json,csv,sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import solve_continuous_lyapunov
sp=importlib.util.spec_from_file_location('c','sessions/claude/T01_N_r1/cand_R1/curves.py');c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
r=list(csv.DictReader(open('T01_truth/C2/curves_C2.csv')))
s={k:np.array([float(x['q_var_m2']) for x in r if x['case']==k+'_template']) for k in ('C1','C2')}
assert len(s['C1'])==601 and len(s['C2'])==601
A0,D1,D2=c.build(0.9783,0.0705); Q=c.Q; kap=c.kappa; Iv=c.Iv
def run(tau,ca=None,P00=False):
    Am=lambda U,cU: A0+kap*cU*D1+kap*Iv*U*U*D2
    Ai=Am(10.0,10.0 if ca is None else ca)
    P0=np.zeros((6,6)) if P00 else solve_continuous_lyapunov(Ai,-Q)
    def f(tt,y):
        P=y.reshape(6,6);U=c.Ufun(tt,tau);A=Am(U,U if ca is None else ca);AP=A@P
        return (AP+AP.T+Q).ravel()
    return solve_ivp(f,(0,600),P0.ravel(),method='DOP853',t_eval=np.arange(0,601.),rtol=1e-9,atol=1e-14,max_step=1.0).y[0]
e=lambda v,s:np.sqrt(((v-s)**2).sum()/(s**2).sum())
for k,tau in (('C1',60.),('C2',10.)):
    b=run(tau); print(k,'base e_L2 %.9f e_pk %+.6f'%(e(b,s[k]),b.max()/s[k].max()-1))
    for n,kw in (('ca10',dict(ca=10.)),('ca30',dict(ca=30.)),('P00',dict(P00=True))):
        v=run(tau,**kw); print(k,n,'d %.3e e_L2 %.5f e_pk %+.4f'%(e(v,b),e(v,s[k]),v.max()/s[k].max()-1))
