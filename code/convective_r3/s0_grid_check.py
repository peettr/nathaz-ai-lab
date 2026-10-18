"""Exact Earth2Studio 0.19.0 HRRR grid point/edge distances for S0 candidates."""
import json,numpy as np,math
from scipy.spatial import cKDTree
from earth2studio.data import HRRR
p='/content/s0_events_provisional.json'; rows=json.load(open(p))
lat,lon=HRRR.grid(); print('HRRR_GRID',lat.shape,flush=True)
for group,ylim,xlim in [('v1',(273,785),(579,1219)),('conus',(17,1041),(3,1795))]:
 la=lat[ylim[0]:ylim[1],xlim[0]:xlim[1]];lo=lon[ylim[0]:ylim[1],xlim[0]:xlim[1]]
 edge_la=np.concatenate((la[0,:],la[-1,:],la[1:-1,0],la[1:-1,-1]));edge_lo=np.concatenate((lo[0,:],lo[-1,:],lo[1:-1,0],lo[1:-1,-1]))
 rad=np.deg2rad(np.stack([la.ravel(),lo.ravel()],axis=-1));xyz=np.stack([np.cos(rad[:,0])*np.cos(rad[:,1]),np.cos(rad[:,0])*np.sin(rad[:,1]),np.sin(rad[:,0])],axis=-1)
 tree=cKDTree(xyz)
 for x in rows:
  if x['group']!=group:continue
  a=math.radians(float(x['lat']));b=math.radians(float(x['lon']));d,ix=tree.query([math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)])
  j,i=np.unravel_index(ix,la.shape);edge_a=np.deg2rad(edge_la);edge_b=np.deg2rad(edge_lo)
  h=np.sin((edge_a-a)/2)**2+np.cos(edge_a)*math.cos(a)*np.sin((edge_b-b)/2)**2
  edge=float((12742*np.arcsin(np.sqrt(np.clip(h,0,1)))).min());nearest=float(12742*math.asin(min(1,d/2)))
  x['grid_y']=int(j);x['grid_x']=int(i);x['grid_nearest_km']=round(nearest,3);x['grid_edge_km']=round(edge,3)
  x['grid_inside']=bool(j not in (0,la.shape[0]-1) and i not in (0,la.shape[1]-1) and nearest<3 and edge>=25)
 print('GROUP',group,'inside',sum(x.get('grid_inside',False) for x in rows if x['group']==group),flush=True)
json.dump(rows,open('/content/s0_grid_checked.json','w'))
