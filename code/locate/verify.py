import json,numpy as np,csv
from PIL import Image,ImageDraw
from scipy import ndimage as ni
from matplotlib.path import Path
R='./tmp_l2613/'
lat0,lon0=37.92943,139.05260
mx=111320*np.cos(np.radians(lat0));my=110940
# STL binary → occupancy from vertices at z>=~1.5
b=open(R+'vox/OpenStreetMap_1m.stl','rb').read();n=int.from_bytes(b[80:84],'little')
a=np.frombuffer(b,dtype=np.dtype([('n','<3f4'),('v','<9f4'),('c','<u2')]),count=n,offset=84)['v'].reshape(-1,3,3)
v=a.reshape(-1,3);print('stl tris',n,'bounds',v.min(0),v.max(0))
# wall facets crossing z=2 → boundary; fill via horizontal top faces at z~9.5
nz=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);top=(np.abs(nz[:,2])/(np.linalg.norm(nz,axis=1)+1e-9)>.5)&(a[:,:,2].min(1)>8)
print('top tris',top.sum())
c=a[top][:,:,:2].mean(1);occ=np.zeros((500,500),bool)
ix=np.clip(np.floor(c[:,0]+.5).astype(int),0,499);iy=np.clip(np.floor(c[:,1]+.5).astype(int),0,499);occ[iy,ix]=True
occ=ni.binary_closing(occ,iterations=1);print('occ frac',occ.mean())
# OSM polygons in local tangent coordinates (true north), origin=AIJ, raster 1m centred
d=json.load(open(R+'osm.json'))['elements']
polys=[np.array([[(p['lon']-lon0)*mx,(p['lat']-lat0)*my] for p in e['geometry']]) for e in d if e.get('geometry') and len(e['geometry'])>=3]
polys=[p for p in polys if np.abs(p).max()<400]
im=Image.new('1',(500,500));dr=ImageDraw.Draw(im)
for p in polys: dr.polygon([tuple(q+250) for q in p],fill=1)
O=np.array(im,dtype=bool);print('osm frac',O.mean(),'polys',len(polys))
# official roof raster with pose rotation -1 about origin (world)
t=np.load(R+'tri.npy')*250;nn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);nn/=np.linalg.norm(nn,axis=1,keepdims=True)+1e-30
T=t[(np.abs(nn[:,2])>.9)&(t[:,:,2].min(1)>.5)]
def rast(deg):
    c,s=np.cos(np.radians(deg)),np.sin(np.radians(deg));r=np.array([[c,-s],[s,c]]);q=T[:,:,:2]@r.T
    i=Image.new('1',(500,500));D=ImageDraw.Draw(i)
    for tri in q: D.polygon([tuple(x+250) for x in tri],fill=1)
    return np.array(i,dtype=bool)
Of0=rast(0)
def iou(A,B): return (A&B).sum()/((A|B).sum()+1e-9)
yy,xx=np.mgrid[:500,:500];disc=np.hypot(xx-250,yy-250)<190
def rot(A,deg): return ni.rotate(A.astype(float),deg,reshape=False,order=0)>.5
print('--- dihedral of VoxCity occ vs official frame (no extra rot)')
for name,F in [('id',occ),('T',occ.T),('fliplr',occ[:,::-1]),('flipud',occ[::-1]),('rot180',occ[::-1,::-1]),('Tflip1',occ.T[::-1]),('Tflip2',occ.T[:,::-1]),('Tboth',occ.T[::-1,::-1])]:
    print(name,round(iou(F&disc,Of0&disc),3))
print('--- rotation scan of occ vs official (rot deg, IoU in disc)')
best=None
for r in np.arange(-4,4.01,.5):
    F=rot(occ,r);u=iou(F&disc,Of0&disc);print(r,round(u,3),end=' | ')
    if best is None or u>best[0]:best=(u,r)
print('\nbest',best)
# measure points
rows=list(csv.DictReader(open(R+'data/RS_caseE.csv',encoding='utf-8-sig')))
P={}
for r in rows:
    if r['case']=='ac':P[int(r['No.'])]=(float(r['x(m)']),float(r['y(m)']))
ids=sorted(P);xy=np.array([P[i] for i in ids]);print('pts',len(xy))
def hits(A,xy):
    ix=np.floor(xy[:,0]+250).astype(int);iy=np.floor(xy[:,1]+250).astype(int);return A[iy,ix]
print('pts in official raster',hits(Of0,xy).sum(),[i for i,h in zip(ids,hits(Of0,xy)) if h])
c,s=np.cos(np.radians(-1)),np.sin(np.radians(-1));W=np.c_[c*xy[:,0]-s*xy[:,1],s*xy[:,0]+c*xy[:,1]]
paths=[Path(p) for p in polys]
insideosm=[i for i,w in zip(ids,W) if any(pp.contains_point(w) for pp in paths)]
print('pts in raw OSM polygons (pose -1deg, true north):',len(insideosm),insideosm)
print('pts in stl occ (as delivered, frame official):',hits(occ,xy).sum(),[i for i,h in zip(ids,hits(occ,xy)) if h])
for r in (best[1],):
    F=rot(occ,r);print('pts in occ after rot',r,hits(F,xy).sum(),[i for i,h in zip(ids,hits(F,xy)) if h])
np.save(R+'occ.npy',occ)
