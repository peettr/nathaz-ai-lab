"""S2a 主动律失效对称建模（卡 §16）。用法: python3 -I s2a_active_fail.py <force.npz> <s2a_v2.json> <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
from scipy.signal import welch
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s2a_rom.py').read().split('def sig(')[0],'defs','exec'),ns)
M,w,ZETA,C=ns['M'],ns['w'],ns['ZETA'],ns['C'];sys_passive=ns['sys_passive'];FL=20000.
z=np.load(sys.argv[1]);dt=float(z['dt']);fw,P=welch(z['force'],fs=1/dt,nperseg=4096,axis=-1);Sw=P.mean(0)
f=np.logspace(np.log10(.005),1,200000);S=np.interp(f,fw,Sw);df=np.gradient(f);om=2*np.pi*f
v2=json.load(open(sys.argv[2]));sb=v2['sigma_bare'];FP=v2['SA']['F_at_C'];Fopen=v2['SA']['F_c0'];Flock=v2['SA']['F_locked']
A,bw,bu=sys_passive();Cm=A[1,:].copy();Du=bu[1];Dw=bw[1];W=float(np.interp(ns['F1'],fw,Sw))/(4*np.pi);Q=np.diag([400.,25.,16.,1.])
def rms(Acl,Bw,Bv,Sv,row):
    lam,V=np.linalg.eig(Acl);Vi=np.linalg.inv(V);G=1/(1j*om[None,:]-lam[:,None])
    tf=lambda b:(row@V*(Vi@b))@G
    return float(np.sqrt(np.sum(np.abs(tf(Bw))**2*S*df)+np.sum(np.abs(tf(Bv))**2*Sv*df)))
rows=[]
for rho in (1e-13,1e-12,1e-11,1e-10,1e-9):
    Pc=la.solve_continuous_are(A,bu[:,None],Q,np.array([[rho]]));K=(bu@Pc)/rho
    for r in (1e-4,1e-2,1.,1e2,1e4):
        Vs=r*W*Dw*Dw;Rb=Vs+W*Dw*Dw;Nb=W*bw*Dw
        Pf=la.solve_continuous_are(A.T,Cm[:,None],W*np.outer(bw,bw),np.array([[Rb]]),s=Nb[:,None]);Lf=(Pf@Cm+Nb)/Rb
        Ak=A-np.outer(bu,K)-np.outer(Lf,Cm)+Du*np.outer(Lf,K)
        def cl(ks):
            # 传感器 y_meas = ks*y_true ; 估计器按名义：xh'=Ak xh + Lf y_meas ；y_true = Cm x + Du u + Dw w + v ; u=-K xh
            Acl=np.block([[A,-np.outer(bu,K)],[ks*np.outer(Lf,Cm),Ak-ks*Du*np.outer(Lf,K)]]);Bw=np.r_[bw,ks*Lf*Dw];Bv=np.r_[np.zeros(4),ks*Lf];return Acl,Bw,Bv
        e0=np.zeros(8);e0[0]=1;eu=np.r_[np.zeros(4),-K];res={}
        for nm,ks in (('nominal',1.),('F3_sign',-1.),('F4_x0.5',.5),('F4_x2',2.),('F5_zero',0.)):
            Acl,Bw,Bv=cl(ks);mx=float(np.max(np.linalg.eigvals(Acl).real))
            if mx>=0:res[nm]=dict(unstable=True,max_re=mx);continue
            s=rms(Acl,Bw,Bv,4*np.pi*Vs,e0);res[nm]=dict(unstable=False,F=(s-sb)/sb)
            if nm=='nominal':res[nm]['u_rms']=rms(Acl,Bw,Bv,4*np.pi*Vs,eu)
        nom=res['nominal'];feas=nom.get('u_rms',1e9)<=FL/3
        rows.append(dict(rho=rho,r=r,feasible=feas,F_A=nom.get('F'),modes=res,F1_off=FP,F2_seized=Flock))
        print('%.0e %.0e feas=%s F_A=%.4f'%(rho,r,feas,nom['F']),{k:('UNSTABLE' if v['unstable'] else round(v['F'],4)) for k,v in res.items() if k!='nominal'},flush=True)
fe=[x for x in rows if x['feasible']];summ={}
for m in ('F3_sign','F4_x0.5','F4_x2','F5_zero'):
    un=sum(x['modes'][m]['unstable'] for x in fe);fin=[x['modes'][m]['F'] for x in fe if not x['modes'][m]['unstable']]
    summ[m]=dict(unstable=un,n=len(fe),worst_F=max(fin) if fin else None)
anyun=any(v['unstable']>0 for v in summ.values());worst=max([v['worst_F'] for v in summ.values() if v['worst_F'] is not None]+[Flock])
verdict='主动律存在无界损失的失效模式（本模型）' if anyun else ('主动律失效不比阻尼失效更危险' if worst<=Fopen else '模式相关')
out=dict(F_P=FP,F_open=Fopen,F_lock=Flock,summary=summ,verdict=verdict,rows=rows);print(summ,verdict)
json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
