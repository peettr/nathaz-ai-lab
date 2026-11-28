"""S2a v2（卡 §12）。用法: python3 -I s2a_v2.py <force.npz> <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
from scipy.signal import welch
from scipy.stats import spearmanr
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s2a_rom.py').read().split('def sig(')[0],'defs','exec'),ns)
M,w,ZETA,C,MD,B,d,K0=ns['M'],ns['w'],ns['ZETA'],ns['C'],ns['MD'],ns['B'],ns['d'],ns['K'];sys_passive=ns['sys_passive'];FL=20000.
z=np.load(sys.argv[1]);dt=float(z['dt']);fw,P=welch(z['force'],fs=1/dt,nperseg=4096,axis=-1);Sw=P.mean(0)
f=np.logspace(np.log10(.005),1,200000);S=np.interp(f,fw,Sw);df=np.gradient(f);om=2*np.pi*f
sigma=lambda H:float(np.sqrt(np.sum(np.abs(H)**2*S*df)))
def resp(A,b,out=0,omv=om):
    n=len(A);return np.array([np.linalg.solve(1j*x*np.eye(n)-A,b)[out] for x in omv])
def resp_fast(A,b,out=0):
    lam,V=np.linalg.eig(A);c=np.linalg.solve(V,b);return (V[out]*c)[None,:]@(1/(1j*om[None,:]-lam[:,None]))
def sig_sys(A,b):return float(np.sqrt(np.sum(np.abs(resp_fast(A,b)[0])**2*S*df)))
Hb=1/(M*(w*w-om**2+2j*ZETA*w*om));sb=sigma(Hb);A,bw,bu=sys_passive();sP=sig_sys(A,bw)
out=dict(sigma_bare=sb,sigma_passive=sP,g=(sb-sP)/sb,g_rom=0.3365484554880872);out['align_ok']=abs(out['g']-out['g_rom'])<=.1;print('align',out['g'],out['align_ok'],flush=True)
# semi-active incl c=0 and locked
cs=np.r_[0.,C*np.logspace(-3,3,200)];Fs=[(sig_sys(sys_passive(c=c)[0],bw)-sb)/sb for c in cs]
ml=M+MD+B*d*d;Hl=1/(M*w*w-ml*om**2+2j*ZETA*M*w*om)  # locked: device rigid with tower top (relative coord fixed)
Flock=(sigma(Hl)-sb)/sb;i=int(np.argmax(Fs))
out['SA']=dict(F_max=float(max(max(Fs),Flock)),worst='locked' if Flock>max(Fs) else float(cs[i]/C),F_c0=float(Fs[0]),F_locked=float(Flock),F_at_C=(sP-sb)/sb,all_neg=bool(max(max(Fs),Flock)<0),curve=[[float(c/C),float(x)] for c,x in zip(cs,Fs)])
print('SA',{k:v for k,v in out['SA'].items() if k!='curve'},flush=True)
omg=2*np.pi*np.logspace(-3,3,20000);Q=np.diag([400.,25.,16.,1.])
def margins(Lw,clfun):
    Sinf=float(max(1.,np.max(np.abs(1/(1+Lw)))));mag=np.abs(Lw);taus=[];pms=[]
    for i in np.where(np.diff(np.sign(mag-1))!=0)[0]:
        lag=(np.angle(Lw[i])+np.pi)%(2*np.pi);pms.append(np.degrees(min(lag,2*np.pi-lag)));taus.append(lag/omg[i])
    gs=np.logspace(-3,3,600);st=np.array([np.max(np.linalg.eigvals(clfun(g)).real)<0 for g in gs]);i1=np.argmin(abs(gs-1))
    lo=i1
    while lo>0 and st[lo-1]:lo-=1
    hi=i1
    while hi<len(gs)-1 and st[hi+1]:hi+=1
    gl=None if lo==0 and st[0] else float(gs[lo]);gh=None if hi==len(gs)-1 and st[-1] else float(gs[hi])
    return dict(Sinf=Sinf,tau_star=float(min(taus)) if taus else None,PM_deg=float(min(pms)) if pms else None,g_low=gl,g_high=gh,eps_high=None if gh is None else gh-1,eps_low=None if gl is None else gl-1,n_cross=len(taus))
# full-state LQR on real spectrum
lqr=[]
for rho in np.logspace(-14,-6,25):
    Pc=la.solve_continuous_are(A,bu[:,None],Q,np.array([[rho]]));K=(bu@Pc)/rho;Acl=A-np.outer(bu,K);s=sig_sys(Acl,bw)
    uf=float(np.sqrt(np.sum(np.abs(([邮箱]([resp_fast(Acl,bw,j)[0] for j in range(4)])))**2*S*df)))
    Lw=np.array([[邮箱](1j*x*np.eye(4)-A,bu) for x in omg]);m=margins(Lw,lambda g:A-g*np.outer(bu,K))
    lqr.append(dict(rho=float(rho),Delta=(sb-s)/sb,R_x=(sP-s)/sP,u_rms=uf,feasible=uf<=FL/3,**m))
    print('LQR %.0e Δ=%.4f Rx=%.4f u=%.0f'%(rho,lqr[-1]['Delta'],lqr[-1]['R_x'],uf),m,flush=True)
out['LQR']=lqr
# LQG correlated noise
Cm=A[1,:].copy();Du=bu[1];Dw=bw[1];i1=np.argmin(abs(f-ns['F1']));W=float(np.interp(ns['F1'],fw,Sw))/(4*np.pi);rows=[];k=0
for rho in (1e-13,1e-12,1e-11,1e-10,1e-9):
    Pc=la.solve_continuous_are(A,bu[:,None],Q,np.array([[rho]]));K=(bu@Pc)/rho
    for r in (1e-4,1e-2,1.,1e2,1e4):
        k+=1;Vs=r*W*Dw*Dw;Rb=Vs+W*Dw*Dw;Nb=W*bw*Dw
        Pf=la.solve_continuous_are(A.T,Cm[:,None],W*np.outer(bw,bw),np.array([[Rb]]),s=Nb[:,None]);Lf=(Pf@Cm+Nb)/Rb
        Ak=A-np.outer(bu,K)-np.outer(Lf,Cm)+Du*np.outer(Lf,K)
        def cl(g,Kx=K,Lx=Lf,Ax=Ak):return np.block([[A,-g*np.outer(bu,Kx)],[np.outer(Lx,Cm),Ax-g*Du*np.outer(Lx,Kx)]])
        Acl=cl(1.);
        if np.max(np.linalg.eigvals(Acl).real)>=0:rows.append(dict(rho=rho,r=r,unstable=True));continue
        Bw=np.r_[bw,Lf*Dw];Bv=np.r_[np.zeros(4),Lf];Sv=4*np.pi*Vs
        lam,V=np.linalg.eig(Acl);Vi=np.linalg.inv(V);G=1/(1j*om[None,:]-lam[:,None])
        def tf(out_row,b):return (out_row@V*(Vi@b))@G
        e0=np.zeros(8);e0[0]=1;eu=np.r_[np.zeros(4),-K]
        s2=np.sum(np.abs(tf(e0,Bw))**2*S*df)+np.sum(np.abs(tf(e0,Bv))**2*Sv*df);s=float(np.sqrt(s2))
        sw_only=float(np.sqrt(np.sum(np.abs(tf(e0,Bw))**2*S*df)))
        uf=float(np.sqrt(np.sum(np.abs(tf(eu,Bw))**2*S*df)+np.sum(np.abs(tf(eu,Bv))**2*Sv*df)))
        Lw=np.array([([邮箱](1j*x*np.eye(4)-Ak,Lf))*([邮箱](1j*x*np.eye(4)-A,bu)+Du) for x in omg]);m=margins(Lw,cl)
        rng=np.random.default_rng(k);dfrag=1.
        for dl in np.logspace(-4,np.log10(.3),15):
            bad=False
            for _ in range(30):
                Kp=K*(1+dl*rng.standard_normal(4));Lp=Lf*(1+dl*rng.standard_normal(4));Ap=Ak*(1+dl*rng.standard_normal((4,4)))
                if np.max(np.linalg.eigvals(cl(1.,Kp,Lp,Ap)).real)>=0:bad=True;break
            if bad:dfrag=float(dl);break
        rows.append(dict(rho=rho,r=r,Delta=(sb-s)/sb,R_x=(sP-s)/sP,Delta_windonly=(sb-sw_only)/sb,u_rms=uf,feasible=uf<=FL/3,delta_frag=dfrag,**m))
        x=rows[-1];print('LQG %.0e %.0e Δ=%.4f Rx=%.4f u=%.0f S∞=%.2f g=[%s,%s] PM=%s τ*=%s δf=%.4f'%(rho,r,x['Delta'],x['R_x'],uf,x['Sinf'],x['g_low'],x['g_high'],x['PM_deg'],x['tau_star'],dfrag),flush=True)
out['LQG']=rows
def spear(rs,key,inv=False):
    D=[x['Delta'] for x in rs];v=[(0 if x[key] is None else 1/x[key]) if inv else x[key] for x in rs]
    return None if len(set(v))<2 else float(spearmanr(D,v).correlation)
ok=[x for x in rows if 'Delta' in x]
for nm,rs in (('LQR',lqr),('LQG',ok),('LQG_feasible',[x for x in ok if x['feasible']])):
    out['spearman_'+nm]=dict(Sinf=spear(rs,'Sinf'),inv_tau=spear(rs,'tau_star',True),n=len(rs))
out['spearman_LQG']['inv_dfrag']=spear(ok,'delta_frag',True)
lost=lambda x:(x['eps_high'] is not None and x['eps_high']<1) or (x['PM_deg'] is not None and x['PM_deg']<30)
out['lost_guarantee_LQG']=sum(lost(x) for x in ok);out['lost_guarantee_LQG_feasible']=sum(lost(x) for x in ok if x['feasible']);out['lost_guarantee_LQR']=sum(lost(x) for x in lqr)
print({k:v for k,v in out.items() if k.startswith('spearman') or k.startswith('lost')})
json.dump(out,open(sys.argv[2],'w'),indent=1)
