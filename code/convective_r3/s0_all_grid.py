"""Exact grid verification of all METAR+radar eligible source rows, not pre-deduplicated."""
import json,numpy as np,math
from scipy.spatial import cKDTree
from earth2studio.data import HRRR
rows=[]
for file in ('s0_radar_checked.jsonl','s0_radar_extra.jsonl'):
 for line in open('/content/'+file):
  r=json.loads(line)
  if r['radar_40']: rows.append(r)
assert len(rows)==578,len(rows)
lat,lon=HRRR.grid()
for group,ylim,xlim in [('v1',(273,785),(579,1219)),('conus',(17,1041),(3,1795))]:
 la=lat[ylim[0]:ylim[1],xlim[0]:xlim[1]];lo=lon[ylim[0]:ylim[1],xlim[0]:xlim[1]]
 edge_la=np.concatenate((la[0,:],la[-1,:],la[1:-1,0],la[1:-1,-1]));edge_lo=np.concatenate((lo[0,:],lo[-1,:],lo[1:-1,0],lo[1:-1,-1]))
 rad=np.deg2rad(np.stack([la.ravel(),lo.ravel()],axis=-1));xyz=np.stack([np.cos(rad[:,0])*np.cos(rad[:,1]),np.cos(rad[:,0])*np.sin(rad[:,1]),np.sin(rad[:,0])],axis=-1)
 tree=cKDTree(xyz);er=np.deg2rad(edge_la);el=np.deg2rad(edge_lo)
 for x in rows:
  if x['group']!=group:continue
  a=math.radians(float(x['lat']));b=math.radians(float(x['lon']));d,ix=tree.query([math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)])
  j,i=np.unravel_index(ix,la.shape)
  h=np.sin((er-a)/2)**2+np.cos(er)*math.cos(a)*np.sin((el-b)/2)**2
  edge=float((12742*np.arcsin(np.sqrt(np.clip(h,0,1)))).min());nearest=float(12742*math.asin(min(1,d/2)))
  x.update(grid_y=int(j),grid_x=int(i),grid_nearest_km=round(nearest,3),grid_edge_km=round(edge,3),grid_inside=bool(j not in (0,la.shape[0]-1) and i not in (0,la.shape[1]-1) and nearest<3 and edge>=25))
 print('GROUP',group,'total',sum(x['group']==group for x in rows),'inside',sum(x.get('grid_inside',False) for x in rows if x['group']==group),flush=True)
with open('/content/s0_all_grid.json','x') as f:json.dump(rows,f)
print('GRID_DONE',len(rows),flush=True)
