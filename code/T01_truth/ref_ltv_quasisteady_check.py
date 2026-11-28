import numpy as np
from scipy.linalg import solve_continuous_lyapunov
from scipy.integrate import solve_ivp
M=437000.; FS=.32; ZS=.01; KAPPA=245.; IU=.12; MU=.01; BETA=.05; PHI=.5
PF=np.array([-1.6461981787050797,.690763033834006,1.0263004204173023,1.254203536706782])
a0,a1,c0,c1=np.exp(PF); AF=np.array([[0.,1.],[-a0,-a1]]); CF=np.array([c0,c1]); BB=np.zeros((6,6)); BB[5,5]=1.
PFLT=solve_continuous_lyapunov(AF,-np.array([[0.,0.],[0.,1.]])); FN=float(np.sqrt(CF@PFLT@CF))
WS=2*np.pi*FS; MASS=np.array([[M+BETA*M*PHI**2,-BETA*M*PHI],[-BETA*M*PHI,(MU+BETA)*M]]); MINV=np.linalg.inv(MASS)
def A(nu,zd,u):
    wd=nu*WS; md=(MU+BETA)*M; kd=md*wd**2; cd=2*zd*md*wd
    a=np.zeros((6,6)); a[:2,2:4]=np.eye(2); a[2:4,:2]=[邮箱]([[M*WS**2+kd,-kd],[-kd,kd]])
    a[2:4,2:4]=[邮箱]([[2*ZS*M*WS+KAPPA*u+cd,-cd],[-cd,cd]])
    a[2:4,4:6]=np.outer(MINV[:,0],CF)*(KAPPA*u)*(IU*u/FN); a[4:6,4:6]=AF; return a
def run(tau,nu=.9783,zd=.0705,T=600,t0=300):
    w=lambda t:10+20*np.exp(-((t-t0)/tau)**2)
    P0=solve_continuous_lyapunov(A(nu,zd,w(0)),-BB)
    f=lambda t,p:(lambda a,P:(a@[邮箱]+BB).ravel())(A(nu,zd,w(t)),p.reshape(6,6))
    ts=np.arange(0,T+.5,.5); s=solve_ivp(f,(0,T),P0.ravel(),t_eval=ts,rtol=1e-8,atol=1e-14)
    vq=s.y[0]; qs=np.array([solve_continuous_lyapunov(A(nu,zd,w(t)),-BB)[0,0] for t in ts])
    i=vq.argmax(); j=qs.argmax()
    return vq.max(),ts[i],qs.max(),ts[j]
for tau in (60,30,15,10,5):
    a,ti,b,tj=run(tau); print(f"tau={tau}: LTV peak {a:.4e} at {ti}  quasi-steady peak {b:.4e} at {tj}  rel {(b/a-1)*100:+.1f}%")
