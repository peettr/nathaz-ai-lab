#!/usr/bin/env python3
"""L22.11 3a 离线算 J（实验卡 ③ 定义）：读 foamToVTK ascii .vtp 的建筑五个面（xneg xpos yneg ypos roof）p，
Cp=2p/U_H²；每个 TPU 测点取 2 m×2 m 方块（在所在面内，截到墙边）内面元的面积加权平均 Cp；J=Σ(Cp_CFD−Cp_exp)²。
FD：dJ_v=(J(v+)−J(v−))/(2h)。用法：python jcalc.py <VTK目录> <TPU派生表.csv> <endpoints.jsonl> <empty_reference.json> <输出json>"""
import sys, json, re, glob, os, numpy as np
vtk, tpu, ends, refp, outp = sys.argv[1:6]
U=float(json.load(open(refp))['U_at_H']); H=1e-3; B=8.0; Hb=8.0
def arr(xml,name):
    m=re.search(r"<DataArray[^>]*Name=[\"']%s[\"'][^>]*>(.*?)</DataArray>"%re.escape(name),xml,re.S)
    if not m: raise ValueError('no '+name)
    return np.array(m.group(1).split(),float)
def read_vtp(p):
    x=open(p).read(); pieces=x.split('<Piece')[1:]; P=[];Cc=[];A=[];V=[]
    for pc in pieces:
        mp=re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>",pc,re.S); pts=np.array(mp.group(1).split(),float)
        pts=pts.reshape(-1,3); con=arr(pc,'connectivity').astype(int); off=arr(pc,'offsets').astype(int); p=arr(pc,'p')
        st=np.r_[0,off[:-1]]; assert len(p)==len(off)
        for a,b,pv in zip(st,off,p):
            q=pts[con[a:b]]; c0=q.mean(0); ar=0.0; cw=np.zeros(3)
            for j in range(1,len(q)-1):
                t=0.5*np.linalg.norm(np.cross(q[j]-q[0],q[j+1]-q[0])); ar+=t; cw+=t*(q[0]+q[j]+q[j+1])/3
            Cc.append(cw/ar if ar>0 else c0); A.append(ar); V.append(pv)
    return np.array(Cc),np.array(A),np.array(V)
# TPU taps → (patch, u, v) in face plane；坐标换算按 R25.1-13（展开图：墙脚线=外侧极值∓1 m）
taps=np.array([l.split(',') for l in open(tpu) if l[0].isdigit()],float)
def tapmap(face,xu,yu):
    if face==1: return 'xneg', yu, xu+26.0     # x=-8 面：(y, z)
    if face==3: return 'xpos', yu, 26.0-xu     # x=+8
    if face==2: return 'yneg', xu, yu+18.0     # y=-8：(x, z)
    if face==4: return 'ypos', xu, 18.0-yu     # y=+8
    if face==5: return 'roof', xu, yu          # z=8：(x, y)
def faceuv(patch,C):
    return {'xneg':C[:,[1,2]],'xpos':C[:,[1,2]],'yneg':C[:,[0,2]],'ypos':C[:,[0,2]],'roof':C[:,[0,1]]}[patch]
lim={'xneg':((-B,B),(0,Hb)),'xpos':((-B,B),(0,Hb)),'yneg':((-B,B),(0,Hb)),'ypos':((-B,B),(0,Hb)),'roof':((-B,B),(-B,B))}
rows=[json.loads(l) for l in open(ends)]
res={'U_at_H':U,'h':H,'endpoints':{}}; Jv={}
for r in rows:
    t=r['time']
    files={pa:sorted(glob.glob(os.path.join(vtk,f'VTK_{t}','**',f'{pa}.vtp'),recursive=True)) for pa in lim}
    geo={}
    for pa,fl in files.items():
        if not fl: raise SystemExit(f'missing vtp {pa} t={t}')
        cs,As,ps=zip(*[read_vtp(f) for f in fl]); geo[pa]=(np.vstack(cs),np.concatenate(As),2*np.concatenate(ps)/U**2)
    cpt=[];nf=[]
    for _,f,xu,yu,ce in taps:
        pa,u,v=tapmap(int(f),xu,yu); C,A,Cp=geo[pa]; UV=faceuv(pa,C); (u0,u1),(v0,v1)=lim[pa]
        lo=(max(u-1,u0),max(v-1,v0)); hi=(min(u+1,u1),min(v+1,v1))
        m=(UV[:,0]>=lo[0])&(UV[:,0]<hi[0])&(UV[:,1]>=lo[1])&(UV[:,1]<hi[1])
        if not m.any(): raise SystemExit(f'empty tile face {f} ({xu},{yu})')
        cpt.append(float((A[m]*Cp[m]).sum()/A[m].sum())); nf.append(int(m.sum()))
    cpt=np.array(cpt); J=float(((cpt-taps[:,4])**2).sum())
    res['endpoints'][r['label']]={'time':t,'J':J,'faces_per_tile_min':int(min(nf)),'faces_per_tile_median':float(np.median(nf)),
        'area_total':{pa:float(g[1].sum()) for pa,g in geo.items()}}
    if r['label']=='BASE': res['tile_cp_base']=cpt.tolist()
    Jv[r['label']]=J
res['dJ']={k:(Jv[k+'_p']-Jv[k+'_m'])/(2*H) for k in ('v2','v3') if k+'_p' in Jv and k+'_m' in Jv}
json.dump(res,open(outp,'w'),indent=1); print(json.dumps({k:v for k,v in res.items() if k!='tile_cp_base'},indent=1))
