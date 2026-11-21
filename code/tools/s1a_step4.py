"""S1a 第四步：在 v9diag 上检验 S1a-P1′/P1″。用法: python3 -I s1a_step4.py <v9.npz> <out.json>"""
import sys,json,importlib.util,numpy as np
here=__file__.rsplit('/',1)[0]
spec=importlib.util.spec_from_file_location('s3',here+'/s1a_step3.py');src=open(here+'/s1a_step3.py').read().split('out={}')[0]
ns={};exec(compile(src,'s1a_step3_defs','exec'),ns)
load,cols,cv,thalf,UP,DIST,FS=ns['load'],ns['cols'],ns['cv'],ns['thalf'],ns['UP'],ns['DIST'],ns['FS']
KAPPA=0.2177;C=0.689
d=np.load(sys.argv[1]);Xf=d['x'];STf=list(d['stations'])
def Tu(g):
    u=Xf[:,3*STf.index(f'{g}_z6')+2];u=u-u.mean();n=len(u);f=np.fft.rfft(u,2*n);r=np.fft.irfft(f*np.conj(f))[:n];r/=r[0]
    k=np.argmax(r<=0);return float(r[:k].sum()/50)
Y,X,ST=load(sys.argv[1]);DEL=[i/2 for i in range(21)];out={}
for g in UP:
    Uc=float(X[:,3*ST.index(f'{g}_z6')+2].mean()*120);tau=DIST[g]/Uc;tu=Tu(g)
    r={D:cv(Y,X[:,cols(ST,[g])],np.arange(int(round(D*FS)),int(round(D*FS))+61,2)) for D in DEL};th=thalf(r)
    Dc=min(DEL,key=lambda D:abs(D-(tau+2)))
    p1=tau+KAPPA*tu;p2=tau+C
    out[g]=dict(U_c=Uc,tau_adv=tau,T_u=tu,R2=r,T_half=th,pred_P1p=p1,pred_P1pp=p2,err_P1p=None if th is None else th-p1,err_P1pp=None if th is None else th-p2,R2_tau2=r[Dc],Dc=Dc)
    print(g,'U=%.3f tau=%.2f Tu=%.2f Th=%s pP1p=%.2f pP1pp=%.2f R2(0)=%.3f R2(%.1f)=%.3f'%(Uc,tau,tu,th if th is None else round(th,2),p1,p2,r[0],Dc,r[Dc]),flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1)
