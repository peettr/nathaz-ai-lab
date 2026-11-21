import json,numpy as np,csv
from PIL import Image,ImageDraw
from scipy import ndimage as ni
from scipy.signal import fftconvolve
R='./tmp_l2613/';lat0,lon0=37.92943,139.05260
mx=111320*np.cos(np.radians(lat0));my=110940
occ=np.load(R+'occ.npy');F0=occ.T
d=json.load(open(R+'osm.json'))['elements']
polys=[np.array([[(p['lon']-lon0)*mx,(p['lat']-lat0)*my] for p in e['geometry']]) for e in d if e.get('geometry') and len(e['geometry'])>=3]
polys=[p for p in polys if np.abs(p).max()<400]
im=Image.new('1',(500,500));dr=ImageDraw.Draw(im)
for p in polys: dr.polygon([tuple(q+250) for q in p],fill=1)
O=np.array(im,dtype=bool)
yy,xx=np.mgrid[:500,:500];disc=np.hypot(xx-250,yy-250)<190
def iou(A,B):return (A&B&disc).sum()/(((A|B)&disc).sum()+1e-9)
res=[]
for r in np.arange(-5,5.01,.25):
    F=ni.rotate(F0.astype(float),r,reshape=False,order=0)>.5
    best=(0,0,0)
    for dy in range(-12,13,1):
        for dx in range(-12,13,1):
            G=np.roll(np.roll(F,dy,0),dx,1);u=iou(G,O)
            if u>best[0]:best=(u,dy,dx)
    res.append((best[0],r,best[1],best[2]))
res.sort(reverse=True);print('VoxCity(T) vs raw OSM true-north, top:',[tuple(round(float(x),3) for x in t) for t in res[:4]])
print('same at rot 0,no shift',round(iou(ni.rotate(F0.astype(float),0,reshape=False,order=0)>.5,O),3))
print('delivered (id) vs OSM',round(iou(occ,O),3))
print('angle implied from rect: ',)
rect=[(139.0497607430098,37.92708497317585),(139.0496393413841,37.93167893790534)]
print('rect west edge bearing deg', np.degrees(np.arctan2((rect[1][0]-rect[0][0])*mx,(rect[1][1]-rect[0][1])*my)))
