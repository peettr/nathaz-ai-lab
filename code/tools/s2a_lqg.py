"""S2a 第二步（卡 §10）。用法: python3 -I s2a_lqg.py <force.npz> <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
from scipy.signal import welch
from scipy.stats import spearmanr
ns={};src=open(__file__.rsplit('/',1)[0]+'/s2a_rom.py').read().split('def sig(')[0];exec(compile(src,'defs','exec'),ns)
M,w,ZETA,C=ns['M'],ns['w'],ns['ZETA'],ns['C'];sys_passive=ns['sys_passive']
z=np.load(sys.argv[1]);dt=float(z['dt']);F=z['force']
f,P=welch(F,fs=1/dt,nperseg=4096,axis=-1);S=P.mean(0);m=(f>=0.005)&(f<=10);f=f[m];S=S[m];df=np.gradient(f);om=2*np.pi*f
def sigma_tf(H):return float(np.sqrt(np.sum(np.abs(H)**2*S*df)))
Hb=1/(M*(w*w-om**2+2j*ZETA*w*om));sb=sigma_tf(Hb)
def H_state(A,b,out=0):return np.array([np.linalg.solve(1j*x*np.eye(len(A))-A,b)[out] for x in om])
A,bw,bu=sys_passive();sP=sigma_tf(H_state(A,bw));out=dict(sigma_bare=sb,sigma_passive=sP,g=(sb-sP)/sb,g_rom=0.3365484554880872)
out['align_ok']=abs(out['g']-out['g_rom'])<=0.10;print('align',out['g'],out['align_ok'],'sb',sb,flush=True)
cs=C*np.logspace(np.log10(.05),np.log10(20),60);Fsa=[(sigma_tf(H_state(sys_passive(c=c)[0],bw))-sb)/sb for c in cs]
out['SA']=dict(F_max=float(max(Fsa)),c_worst_over_C=float(cs[int(np.argmax(Fsa))]/C),F_at_C=(sP-sb)/sb);print('SA',out['SA'],flush=True)
Cm=A[1,:].copy();Du=bu[1];Dw=bw[1]
i1=np.argmin(abs(f-ns['F1']));W=S[i1]/2/(2*np.pi)  # 双边每 rad/s 近似
Q=np.diag([400.,25.,16.,1.]);omg=2*np.pi*np.logspace(-2,1,4000);rng=np.random.default_rng(0);rows=[]
def stable(Mx):return np.max(np.linalg.eigvals(Mx).real)<0
for rho in (1e-13,1e-12,1e-11,1e-10,1e-9):
    Pc=la.solve_continuous_are(A,bu[:,None],Q,np.array([[rho]]));K=(bu@Pc)/rho
    for r in (1e-4,1e-2,1.,1e2,1e4):
        V=r*W*Dw*Dw;Pf=la.solve_continuous_are(A.T,Cm[:,None],W*np.outer(bw,bw),np.array([[V]]));Lf=(Pf@Cm)/V
        def closed(K,Lf,Ak,g=1.):
            # x'=Ax+bw w+bu g u ; xh'=Ak xh + Lf y ; y=Cm x+Du g u+Dw w ; u=-K xh
            Acl=np.block([[A,-g*np.outer(bu,K)],[np.outer(Lf,Cm),Ak-g*Du*np.outer(Lf,K)]]);Bcl=np.r_[bw,Lf*Dw];return Acl,Bcl
        Ak=A-np.outer(bu,K)-np.outer(Lf,Cm)+Du*np.outer(Lf,K)
        # note Ak above already contains +Lf*Du*K from u=-K xh; closed() with g adds plant-side gain on u only
        Ak0=A-np.outer(bu,K)-np.outer(Lf,Cm)  # estimator using known u: xh'=A xh+bu u+Lf(y-Cm xh-Du u)
        def cl(g=1.,Kx=K,Lx=Lf,Ax=Ak0):
            # estimator assumes nominal u; plant receives g*u
            Acl=np.block([[A,-g*np.outer(bu,Kx)],[np.outer(Lx,Cm),Ax+np.outer(Lx,-Du*g*Kx)+Du*np.outer(Lx,Kx)]]);Bcl=np.r_[bw,Lx*Dw];return Acl,Bcl
        Acl,Bcl=cl()
        if not stable(Acl):rows.append(dict(rho=rho,r=r,unstable_nominal=True));continue
        Hy=np.array([np.linalg.solve(1j*x*np.eye(8)-Acl,Bcl)[0] for x in om]);sc=sigma_tf(Hy)
        Hu=np.array([(-np.r_[np.zeros(4),K])@np.linalg.solve(1j*x*np.eye(8)-Acl,Bcl) for x in om]);urms=sigma_tf(Hu)
        def Lof(s):
            G=[邮箱](s*np.eye(4)-A,bu)+Du;Kc=[邮箱](s*np.eye(4)-Ak,Lf);return Kc*G
        Lw=np.array([Lof(1j*x) for x in omg]);Sinf=float(np.max(np.abs(1/(1+Lw))))
        eh=None
        if not stable(cl(101.)[0]):
            a,b=1.,101.
            for _ in range(50):
                mm=(a+b)/2;a,b=(mm,b) if stable(cl(mm)[0]) else (a,mm)
            eh=a-1
        el=None
        if not stable(cl(1e-6)[0]):
            a,b=1e-6,1.
            for _ in range(50):
                mm=(a+b)/2;a,b=(a,mm) if stable(cl(mm)[0]) else (mm,b)
            el=b-1
        mag=np.abs(Lw);ph=np.angle(-Lw);taus=[];pms=[]
        for i in np.where(np.diff(np.sign(mag-1))!=0)[0]:
            pm=abs(np.angle(-1/Lw[i]*-1)) if False else abs(np.pi-abs(np.angle(Lw[i])));pms.append(np.degrees(pm));taus.append(pm/omg[i])
        tau=float(min(taus)) if taus else float('inf');pm=float(min(pms)) if pms else float('inf')
        dfrag=1.
        for dl in np.logspace(-4,np.log10(.3),15):
            bad=False
            for _ in range(30):
                Kp=K*(1+dl*rng.standard_normal(4));Lp=Lf*(1+dl*rng.standard_normal(4));Ap=Ak0*(1+dl*rng.standard_normal((4,4)))
                if not stable(cl(1.,Kp,Lp,Ap)[0]):bad=True;break
            if bad:dfrag=float(dl);break
        row=dict(rho=rho,r=r,sigma=sc,Delta=(sb-sc)/sb,R_x=(sP-sc)/sP,u_rms=urms,Sinf=Sinf,eps_low=el,eps_high=eh,PM_deg=pm,tau_star=tau,delta_frag=dfrag);rows.append(row)
        print('rho %.0e r %.0e Δ=%.4f Rx=%.4f u=%.0f S∞=%.2f ε=[%s,%s] PM=%.1f τ*=%.3f δf=%.4f'%(rho,r,row['Delta'],row['R_x'],urms,Sinf,el,eh,pm,tau,dfrag),flush=True)
out['LQG']=rows;ok=[x for x in rows if 'Delta' in x];D=[x['Delta'] for x in ok]
out['spearman']=dict(Sinf=float(spearmanr(D,[x['Sinf'] for x in ok]).correlation),inv_tau=float(spearmanr(D,[1/x['tau_star'] for x in ok]).correlation),inv_dfrag=float(spearmanr(D,[1/x['delta_frag'] for x in ok]).correlation))
out['lost_guarantee']=any((x['eps_high'] is not None and x['eps_high']<1) or x['PM_deg']<30 for x in ok);print(out['spearman'],'lost',out['lost_guarantee'])
json.dump(out,open(sys.argv[2],'w'),indent=1)
