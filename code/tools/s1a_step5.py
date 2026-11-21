"""S1a 第五步：FIR 窗长 3/6/9 s 敏感性。用法: python3 -I s1a_step5.py <out.json> <name=npz>..."""
import sys,json,numpy as np
here=__file__.rsplit('/',1)[0];ns={};exec(compile(open(here+'/s1a_step3.py').read().split('out={}')[0],'defs','exec'),ns)
load,cols,cv,thalf,UP,DIST,FS=ns['load'],ns['cols'],ns['cv'],ns['thalf'],ns['UP'],ns['DIST'],ns['FS']
DEL=[i/2 for i in range(17)];out={}
for arg in sys.argv[2:]:
    name,p=arg.split('=',1);Y,X,ST=load(p);out[name]={}
    for W in (3,6,9):
        rs=[];out[name][W]={}
        for g in UP:
            tau=DIST[g]/float(X[:,3*ST.index(f'{g}_z6')+2].mean()*120)
            r={D:cv(Y,X[:,cols(ST,[g])],np.arange(int(round(D*FS)),int(round(D*FS))+W*FS+1,2)) for D in DEL};th=thalf(r)
            out[name][W][g]=dict(tau=tau,T_half=th,resid=None if th is None else th-tau,R2_0=r[0]);rs.append(th-tau)
        out[name][W]['c']=float(np.mean(rs));print(name,W,'resid',[round(x,3) for x in rs],'c=%.3f'%np.mean(rs),flush=True)
        json.dump(out,open(sys.argv[1],'w'),indent=1)
