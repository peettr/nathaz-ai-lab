import json,numpy as np,csv
from PIL import Image,ImageDraw
from scipy import ndimage as ni
from scipy.signal import fftconvolve
R='./tmp_l2613/';RES=2.0;lat0,lon0=37.92,139.05
mx=111320*np.cos(np.radians(lat0));my=110940
d=json.load(open(R+'osm.json'))['elements'];polys=[];tags=[]
for e in d:
    g=e.get('geometry')
    if g and len(g)>=3: polys.append(np.array([[(p['lon']-lon0)*mx,(p['lat']-lat0)*my] for p in g]));tags.append(e.get('tags',{}))
al=np.vstack(polys);x0,y0=al.min(0);x1,y1=al.max(0);W,H=int((x1-x0)/RES)+1,int((y1-y0)/RES)+1
im=Image.new('1',(W,H));dr=ImageDraw.Draw(im)
for p in polys: dr.polygon([((a-x0)/RES,(b-y0)/RES) for a,b in p],fill=1)
O=np.array(im,dtype=np.float32)
t=np.load(R+'tri.npy')*250;n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1,keepdims=True)+1e-30
T=t[(np.abs(n[:,2])>0.9)&(t[:,:,2].min(1)>0.5)]
L=210;N=int(2*L/RES)
def lay(th,res=RES):
    c,s=np.cos(th),np.sin(th);r=np.array([[c,-s],[s,c]]);q=T[:,:,:2]@r.T;Z=T[:,:,2].mean(1)
    i=Image.new('I',(N,N));dd=ImageDraw.Draw(i)
    for tri,z in sorted(zip(q,Z),key=lambda a:a[1]): dd.polygon([((a+L)/RES,(b+L)/RES) for a,b in tri],fill=int(round(z*2))+1)
    return np.array(i)
yy,xx=np.mgrid[:N,:N];disc=((xx-N/2)**2+(yy-N/2)**2<=(200/RES)**2)
# NCC over all rotations (post-hoc control)
ncc=[]
D=disc.astype(np.float32)
sO=fftconvolve(O,D[::-1,::-1],mode='valid');n0=D.sum()
for deg in range(-10,11):
    A=(lay(np.radians(deg))>0).astype(np.float32)*D
    ov=fftconvolve(O,A[::-1,::-1],mode='valid');ma=A.sum()/n0;mo=sO/n0
    c=(ov/n0-ma*mo)/np.sqrt(ma*(1-ma)*np.maximum(mo*(1-mo),1e-4))
    ncc.append((deg,c));k=np.unravel_index(c.argmax(),c.shape);print('ncc',deg,round(float(c.max()),3),k)
deg,c=max(ncc,key=lambda r:r[1].max());k=np.unravel_index(c.argmax(),c.shape)
I=np.indices(c.shape);comp=max(float(r[1][np.hypot(I[0]-k[0],I[1]-k[1])*RES>100].max()) for r in ncc)
print('NCC best',deg,float(c.max()),'comp',comp,'ratio',float(c.max())/comp,k)
def count(deg,row,col):
    G=lay(np.radians(deg));lab=np.zeros_like(G);nn=0
    for v in np.unique(G[G>0]):
        l,m=ni.label(G==v);lab[l>0]=l[l>0]+nn;nn+=m
    cx,cy=x0+(col+N/2)*RES,y0+(row+N/2)*RES;cnt=0;hs=[]
    areas=np.bincount(lab.ravel());best={}
    for p,tg in zip(polys,tags):
        q=(p-[cx,cy]+L)/RES
        if np.hypot(*(q.mean(0)-N/2))*RES>190: continue
        i=Image.new('1',(N,N));ImageDraw.Draw(i).polygon([tuple(a) for a in q],fill=1);B=np.array(i)
        if B.sum()<4: continue
        ls=lab[B];ls=ls[ls>0]
        if ls.size==0: continue
        li=np.bincount(ls).argmax();u=(lab==li)[B].sum()/((lab==li)|B).sum()
        if u>best.get(li,0): best[li]=u
    return nn,sum(v>=.5 for v in best.values()),cx,cy
print('count official(best pose)',count(-1,1552,1349));print('count at IoU competitor',count(-9,1384,2446))
# 50 random null poses
rng=np.random.default_rng(0);nl=[]
for _ in range(12):
    r,co=rng.integers(0,c.shape[0]),rng.integers(0,c.shape[1]);nl.append(count(int(rng.integers(-10,11)),r,co)[1])
print('null counts',nl)
cx,cy=x0+(1349+N/2)*RES,y0+(1552+N/2)*RES;print('origin',lat0+cy/my,lon0+cx/mx)
inside=[tg for p,tg in zip(polys,tags) if np.hypot(*(p.mean(0)-[cx,cy]))<353]
print('in 500x500 approx',len(inside),'height',sum('height' in a for a in inside),'levels',sum('building:levels' in a for a in inside))
print('named',[a.get('name') for a in inside if a.get('name')][:15])
