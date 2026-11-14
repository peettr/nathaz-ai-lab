import json,numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as ni
from scipy.signal import fftconvolve
R='./tmp_l2613/'
RES=2.0; lat0,lon0=37.92,139.05
mx=111320*np.cos(np.radians(lat0)); my=110940
d=json.load(open(R+'osm.json'))['elements']
polys=[];H=[]
for e in d:
    g=e.get('geometry')
    if not g or len(g)<3: continue
    polys.append(np.array([[(p['lon']-lon0)*mx,(p['lat']-lat0)*my] for p in g]));H.append(e.get('tags',{}))
all=np.vstack(polys);x0,y0=all.min(0);x1,y1=all.max(0)
W,Ht=int((x1-x0)/RES)+1,int((y1-y0)/RES)+1
im=Image.new('1',(W,Ht));dr=ImageDraw.Draw(im)
for p in polys: dr.polygon([((a-x0)/RES,(b-y0)/RES) for a,b in p],fill=1)
O=np.array(im,dtype=np.float32)
print('osm raster',O.shape,'cover',O.mean())
t=np.load(R+'tri.npy')*250
n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1,keepdims=True)+1e-30
roof=(np.abs(n[:,2])>0.9)&(t[:,:,2].min(1)>0.5)
T=t[roof];print('roof tris',len(T))
def tmpl(th):
    c,s=np.cos(th),np.sin(th);r=np.array([[c,-s],[s,c]])
    q=T[:,:,:2]@r.T
    L=210;N=int(2*L/RES)
    i=Image.new('1',(N,N));dd=ImageDraw.Draw(i)
    for tri in q: dd.polygon([((a+L)/RES,(b+L)/RES) for a,b in tri],fill=1)
    return np.array(i,dtype=np.float32),L
yy=None;res=[]
for deg in range(-10,11):
    A,L=tmpl(np.radians(deg));N=A.shape[0]
    yy,xx=np.mgrid[:N,:N];disc=((xx-N/2)**2+(yy-N/2)**2<=(200/RES)**2).astype(np.float32)
    ov=fftconvolve(O,A[::-1,::-1],mode='valid');bs=fftconvolve(O,disc[::-1,::-1],mode='valid')
    iou=ov/(A.sum()+bs-ov+1e-6)
    res.append((deg,iou));k=np.unravel_index(iou.argmax(),iou.shape)
    print(deg,round(float(iou.max()),4),k,flush=True)
best=max(res,key=lambda r:r[1].max());deg,iou=best
k=np.unravel_index(iou.argmax(),iou.shape);m=iou[k]
yyg,xxg=np.mgrid[:iou.shape[0],:iou.shape[1]]
out=(np.hypot(yyg-k[0],xxg-k[1])*RES>100)
comp=max(float(r[1][np.hypot(np.indices(r[1].shape)[0]-k[0],np.indices(r[1].shape)[1]-k[1])*RES>100].max()) for r in res)
A,L=tmpl(np.radians(deg));N=A.shape[0]
cx,cy=x0+(k[1]+N/2)*RES,y0+(k[0]+N/2)*RES
lon,lat=lon0+cx/mx,lat0+cy/my
print('BEST deg',deg,'iou',float(m),'competitor',comp,'ratio',float(m)/comp,'origin lat lon',lat,lon)
# per-OSM-building match
lab,nl=ni.label(A);cnt=0;tot=0;hit=[]
for p,tg in zip(polys,H):
    q=(p-[cx,cy]+L)/RES
    if np.hypot(*(q.mean(0)-N/2))*RES>190: continue
    tot+=1;i=Image.new('1',(N,N));ImageDraw.Draw(i).polygon([tuple(a) for a in q],fill=1);B=np.array(i)
    if B.sum()<4: continue
    ls=lab[B];ls=ls[ls>0]
    if ls.size==0: continue
    l=np.bincount(ls).argmax();C=lab==l;u=(C&B).sum()/(C|B).sum()
    if u>=.5: cnt+=1;hit.append(float(u))
print('osm bldgs in disc',tot,'template comps',nl,'matched IoU>=.5',cnt,'height tags in disc',sum(1 for p,tg in zip(polys,H) if np.hypot(*(p.mean(0)-[cx,cy]))<190 and 'height' in tg),'levels',sum(1 for p,tg in zip(polys,H) if np.hypot(*(p.mean(0)-[cx,cy]))<190 and 'building:levels' in tg))
