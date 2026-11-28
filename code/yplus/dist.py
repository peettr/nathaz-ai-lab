#!/usr/bin/env python3
"""L22.11 y+ 诊断离线部分（实验卡 EXPERIMENT_CARD_yplus.md ③，11-24 09:07 写定）。
逐测点 dJ 贡献 c_i，Σc_i=dJ·v；若给出 yPlus 的 vtp 目录，再做测点方块 y+ 和面积分段。用法：python3 -I dist.py [yplus根目录]"""
import sys, os, re, glob, json, numpy as np
H=os.path.dirname(os.path.abspath(__file__)); TPU=H+'/../3a/data/TPU_g080400_theta000_meanCp.csv'
U=9.929988929927756; h=1e-3; B=8.0
def arr(x,name):
    m=re.search(r"<DataArray[^>]*Name=[\"']%s[\"'][^>]*>(.*?)</DataArray>"%re.escape(name),x,re.S); return np.array(m.group(1).split(),float)
def read_vtp(p,field):
    x=open(p).read(); C=[];A=[];V=[]
    for pc in x.split('<Piece')[1:]:
        pts=np.array(re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>",pc,re.S).group(1).split(),float).reshape(-1,3)
        con=arr(pc,'connectivity').astype(int); off=arr(pc,'offsets').astype(int); f=arr(pc,field); st=np.r_[0,off[:-1]]
        for a,b,v in zip(st,off,f):
            q=pts[con[a:b]]; ar=0.; cw=np.zeros(3)
            for j in range(1,len(q)-1):
                t=.5*np.linalg.norm(np.cross(q[j]-q[0],q[j+1]-q[0])); ar+=t; cw+=t*(q[0]+q[j]+q[j+1])/3
            C.append(cw/ar); A.append(ar); V.append(v)
    return np.array(C),np.array(A),np.array(V)
P=['xneg','xpos','yneg','ypos','roof']
taps=np.array([l.split(',') for l in open(TPU) if l[0].isdigit()],float)
def tapmap(f,xu,yu): return {1:('xneg',yu,xu+26),3:('xpos',yu,26-xu),2:('yneg',xu,yu+18),4:('ypos',xu,18-yu),5:('roof',xu,yu)}[int(f)]
def uv(pa,C): return C[:,[1,2]] if pa in('xneg','xpos') else (C[:,[0,2]] if pa in('yneg','ypos') else C[:,[0,1]])
lim={p:((-B,B),(0,B)) for p in P[:4]}; lim['roof']=((-B,B),(-B,B))
def tiles(geo):
    out=[]
    for _,f,xu,yu,_ in taps:
        pa,u,v=tapmap(f,xu,yu); C,A,X=geo[pa]; UV=uv(pa,C); (u0,u1),(v0,v1)=lim[pa]
        m=(UV[:,0]>=max(u-1,u0))&(UV[:,0]<min(u+1,u1))&(UV[:,1]>=max(v-1,v0))&(UV[:,1]<min(v+1,v1))
        out.append((A[m]*X[m]).sum()/A[m].sum())
    return np.array(out)
def load(d,field,scale=1.):
    return {pa:(lambda c,a,v:(c,a,v*scale))(*[np.concatenate(z) if i else np.vstack(z) for i,z in enumerate(zip(*[read_vtp(f,field) for f in sorted(glob.glob(f'{d}/**/{pa}.vtp',recursive=True))]))]) for pa in P}
face=taps[:,1].astype(int); fname={1:'xneg迎风',2:'yneg侧',3:'xpos背风',4:'ypos侧',5:'roof'}
lead=(face==5)&(taps[:,2]<=-8+2)   # 屋面前缘带：距迎风边 x=-8 的 2 m 以内（tap x ≤ -6）
res={}; cs={}
for g in ('medium','fine','finer'):
    E={json.loads(l)['label']:json.loads(l)['time'] for l in open(f'{H}/vtk/{g}/l22_endpoints.jsonl')}
    cp={lab:tiles(load(f'{H}/vtk/{g}/VTK_{t}','p',2/U**2)) for lab,t in E.items()}
    for k in ('v2','v3'):
        c=((cp[k+'_p']-taps[:,4])**2-(cp[k+'_m']-taps[:,4])**2)/(2*h); cs[(g,k)]=c
        a=np.abs(c); o=np.argsort(-a); top=o[:18]
        res[f'{g}_{k}']=dict(dJ=float(c.sum()),sum_abs=float(a.sum()),cancel=float(abs(c.sum())/a.sum()),top10pct_share=float(a[top].sum()/a.sum()),
            top10pct_faces={fname[f]:int((face[top]==f).sum()) for f in fname},roof_leading_share=float(a[lead].sum()/a.sum()),
            face_share={fname[f]:float(a[face==f].sum()/a.sum()) for f in fname})
for k in ('v2','v3'):
    for g0,g1 in (('medium','fine'),('fine','finer')):
        d=np.abs(cs[(g1,k)]-cs[(g0,k)]); res[f'delta_{g0}_{g1}_{k}']=dict(sum_abs=float(d.sum()),face_share={fname[f]:float(d[face==f].sum()/d.sum()) for f in fname},roof_leading_share=float(d[lead].sum()/d.sum()),
            corr=float(np.corrcoef(cs[(g0,k)],cs[(g1,k)])[0,1]))
if len(sys.argv)>1:
    Y=sys.argv[1]; yp={}
    for g in ('medium','fine','finer'):
        geo=load(f'{Y}/{g}','yPlus'); yp[g]=tiles(geo)
        seg={}
        for pa,(C,A,V) in geo.items():
            o=np.argsort(V); cw=np.cumsum(A[o])/A.sum()
            seg[pa]=dict(lt5=float(A[V<5].sum()/A.sum()),b5_30=float(A[(V>=5)&(V<=30)].sum()/A.sum()),gt30=float(A[V>30].sum()/A.sum()),
                         median=float(V[o][np.searchsorted(cw,.5)]),p95=float(V[o][np.searchsorted(cw,.95)]))
        res[f'yplus_{g}']=seg
        buf=(yp[g]>=5)&(yp[g]<=30); res[f'yplus_{g}']['taps_in_buffer_share']=float(buf.mean())
        for k in ('v2','v3'):
            a=np.abs(cs[(g,k)]); res[f'{g}_{k}']['abs_c_share_in_buffer']=float(a[buf].sum()/a.sum())
    for k in ('v2','v3'):
        for g0,g1 in (('medium','fine'),('fine','finer')):
            d=np.abs(cs[(g1,k)]-cs[(g0,k)]); buf=(yp[g0]>=5)&(yp[g0]<=30); res[f'delta_{g0}_{g1}_{k}']['share_in_buffer_of_coarser']=float(d[buf].sum()/d.sum())
    np.save(H+'/tap_yplus.npy',np.vstack([yp[g] for g in ('medium','fine','finer')]))
np.save(H+'/tap_c.npy',np.vstack([cs[(g,k)] for g in ('medium','fine','finer') for k in ('v2','v3')]))
json.dump(res,open(H+'/dist_numbers.json','w'),ensure_ascii=False,indent=1); print(json.dumps(res,ensure_ascii=False,indent=1))
