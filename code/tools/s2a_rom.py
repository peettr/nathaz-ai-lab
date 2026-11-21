"""S2a 线性 ROM 分析（卡 §8）。用法: python3 -I s2a_rom.py <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
from scipy.stats import spearmanr
M=404257.4322971429;F1=0.3226;ZETA=0.0038891541;MD=20212.871614857148;B=151596.5371114286;K=510003.61853995034;C=118405.0135084592
SHAPE=(1.385,-1.7684,3.0871,-2.2395,.5357);H=87.6;T=43.8
phi=lambda z:sum(a*(z/H)**i for i,a in enumerate(SHAPE,2))/sum(SHAPE);d=1-phi(T);w=2*np.pi*F1
SIG_BARE=0.015493585449719235;G_ROM=0.3365484554880872;FL=20000.
def sys_passive(k=K,c=C,w1=w):
    Mm=np.array([[M+MD+B*d*d,MD+B*d],[MD+B*d,MD+B]]);Ki=la.solve(Mm,np.array([[M*w1*w1,0],[0,k]]));Ci=la.solve(Mm,np.array([[2*ZETA*M*w1,0],[0,c]]))
    A=np.zeros((4,4));A[0,1]=A[2,3]=1;A[[1,3]][:,[0,2]]=0
    A[1,0],A[1,2]=-Ki[0];A[3,0],A[3,2]=-Ki[1];A[1,1],A[1,3]=-Ci[0];A[3,1],A[3,3]=-Ci[1]
    bw=la.solve(Mm,[1.,0.]);bu=la.solve(Mm,[0.,1.])
    return A,np.array([0,bw[0],0,bw[1]]),np.array([0,bu[0],0,bu[1]])
def sig(A,bw,S0):
    if np.max(np.linalg.eigvals(A).real)>=0:return np.inf
    P=la.solve_continuous_lyapunov(A,-S0*np.outer(bw,bw));return float(np.sqrt(P[0,0]))
Ab=np.array([[0,1],[-w*w,-2*ZETA*w]]);bb=np.array([0,1/M])
Pb=la.solve_continuous_lyapunov(Ab,-np.outer(bb,bb));S0=SIG_BARE**2/Pb[0,0]
A,bw,bu=sys_passive();sP=sig(A,bw,S0);out={'S0':S0,'sigma_bare':SIG_BARE,'sigma_passive':sP,'g_white':(SIG_BARE-sP)/SIG_BARE,'g_rom':G_ROM}
out['align_ok']=abs(out['g_white']-G_ROM)<=0.10;print('align',out['g_white'],G_ROM,out['align_ok'],flush=True)
# semi-active stuck
cs=C*np.logspace(np.log10(.05),np.log10(20),60);F=[(sig(sys_passive(c=c)[0],bw,S0)-SIG_BARE)/SIG_BARE for c in cs]
out['SA']=dict(F_max=float(max(F)),c_worst_over_C=float(cs[int(np.argmax(F))]/C),F_at_C=float((sP-SIG_BARE)/SIG_BARE),F_curve=[[float(c/C),float(f)] for c,f in zip(cs,F)])
out['P_kdrift']={str(s):float((sig(sys_passive(k=K*(1+s))[0],bw,S0)-SIG_BARE)/SIG_BARE) for s in (-.2,-.1,.1,.2)}
out['P_wdrift']={str(s):float((sig(sys_passive(w1=w*(1+s))[0],bw,S0)-SIG_BARE)/SIG_BARE) for s in (-.1,-.05,.05,.1)}
# active LQR
Q=np.diag([400.,25.,16.,1.]);om=2*np.pi*np.logspace(-2,1,4000);rows=[]
def Lfun(Kg,s):return ([邮箱](s*np.eye(4)-A,bu))
for rho in np.logspace(-14,-6,25):
    P=la.solve_continuous_are(A,bu[:,None],Q,np.array([[rho]]));Kg=(bu@P)/rho;Acl=A-np.outer(bu,Kg)
    s_cl=sig(Acl,bw,S0);Pc=la.solve_continuous_lyapunov(Acl,-S0*np.outer(bw,bw));uf=float(np.sqrt(Kg@Pc@Kg))
    Lw=np.array([Lfun(Kg,1j*x) for x in om]);Sw=1/(1+Lw);Sinf=float(np.max(np.abs(Sw)))
    def stable(e):return np.max(np.linalg.eigvals(A-(1+e)*np.outer(bu,Kg)).real)<0
    lo,hi=-1.,0.
    eps_low=None
    if not stable(-1.):
        a,b=-1.,0.
        for _ in range(60):
            m=(a+b)/2;a,b=(m,b) if not stable(m) else (a,m)
        eps_low=b
    a,b=0.,100.;eps_high=None
    if not stable(100.):
        for _ in range(60):
            m=(a+b)/2;a,b=(m,b) if stable(m) else (a,m)
        eps_high=a
    mag=np.abs(Lw);ph=np.angle(Lw);taus=[]
    for i in np.where(np.diff(np.sign(mag-1))!=0)[0]:
        wc=om[i];pm=np.pi+ph[i];pm=(pm+np.pi)%(2*np.pi)-np.pi
        taus.append(abs(pm)/wc)
    tau=float(min(taus)) if taus else float('inf')
    # Bode integral (wide band)
    wb=2*np.pi*np.logspace(-3,np.log10(50),20000);lnS=np.log(np.abs(1/(1+np.array([Lfun(Kg,1j*x) for x in wb]))));I=np.trapz(lnS,wb);Iabs=np.trapz(np.abs(lnS),wb)
    amp=om[np.abs(Sw)>1]/(2*np.pi)
    rows.append(dict(rho=float(rho),sigma=s_cl,Delta=(SIG_BARE-s_cl)/SIG_BARE,R_x=(sP-s_cl)/sP,u_rms=uf,feasible=uf<=FL/3,Sinf=Sinf,eps_low=eps_low,eps_high=eps_high,tau_star=tau,bode_rel=float(I/Iabs) if Iabs>0 else 0.,amp_band_hz=[float(amp.min()),float(amp.max())] if len(amp) else None))
    r=rows[-1];print('rho %.1e Δ=%.4f Rx=%.4f u=%.0fN S∞=%.3f ε=[%s,%s] τ*=%.3f bode=%.3f'%(rho,r['Delta'],r['R_x'],uf,Sinf,eps_low,eps_high,tau,r['bode_rel']),flush=True)
out['A']=rows
D=[r['Delta'] for r in rows];out['spearman_D_Sinf']=float(spearmanr(D,[r['Sinf'] for r in rows]).correlation);out['spearman_D_invtau']=float(spearmanr(D,[1/r['tau_star'] for r in rows]).correlation)
print('SA',out['SA']['F_max'],out['SA']['c_worst_over_C'],'kdrift',out['P_kdrift'],'wdrift',out['P_wdrift'],'spearman',out['spearman_D_Sinf'],out['spearman_D_invtau'])
json.dump(out,open(sys.argv[1],'w'),indent=1)
