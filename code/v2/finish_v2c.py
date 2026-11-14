import os,time,json,traceback,hashlib,zipfile,subprocess,resource
from pathlib import Path
P=Path('/content/l2613v2');P.mkdir(exist_ok=True)
D={'started':time.time(),'sources':{},'error':None,'stage':'init'}
def save(): (P/'finish3.json').write_text(json.dumps(D,ensure_ascii=False,indent=2,default=str))
def log(*x): print(time.strftime('%H:%M:%S'),*x,flush=True);D['stage']=' '.join(map(str,x));save()
def dig(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return {'bytes':p.stat().st_size,'sha256':h.hexdigest(),'mtime':p.stat().st_mtime}
try:
 log('install')
 subprocess.run(['pip','install','-q','git+https://github.com/kunifujiwara/VoxCity.git@61ff5547e6fa9079dcd23c1cb4d37ec793194277','trimesh','rtree','xlrd','scikit-image'],check=True,timeout=900)
 import numpy as np,pandas as pd,geopandas as gpd,trimesh,requests
 from pyproj import CRS,Transformer
 from shapely.ops import transform
 from scipy.ndimage import distance_transform_edt,binary_erosion,label
 from scipy.spatial import cKDTree
 from skimage.morphology import skeletonize
 from rasterio.features import rasterize
 from affine import Affine
 from voxcity.generator import get_voxcity
 lat,lon=37.92943,139.05260;theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
 ll=CRS.from_epsg(4326);ae=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs');fwd=Transformer.from_crs(ll,ae,always_xy=True);inv=Transformer.from_crs(ae,ll,always_xy=True)
 def togeo(x,y):return inv.transform(c*x-s*y,s*x+c*y)
 def tooff(x,y):
  e,n=fwd.transform(x,y);return c*e+s*n,-s*e+c*n
 rect=[togeo(x,y) for x,y in [(-250,-250),(-250,250),(250,250),(250,-250)]]
 def mask(geoms,step=.25,half=205):
  n=round(2*half/step);return rasterize([(g,1) for g in geoms if g is not None and not g.is_empty],out_shape=(n,n),transform=Affine(step,0,-half,0,step,-half),dtype='uint8').astype(bool)
 def iou(a,b,disc):return float(((a&b)&disc).sum()/max(1,((a|b)&disc).sum()))
 def srcmask(g):return mask([transform(tooff,x) for x in g.to_crs(ll).geometry if x is not None],1,250)
 for src in ['OpenStreetMap','Overture']:
  log('source',src);g=gpd.read_file(P/(src+'.gpkg'))
  if g.crs is None:
   assert src=='Overture';g=g.set_crs('EPSG:4326');D['crs_repair']='Overture.gpkg lacked CRS; geometry lon/lat; assigned EPSG:4326'
  off=srcmask(g);d=D['sources'][src]={'records':len(g),'fields':list(g.columns),'height_nonnull':int(pd.to_numeric(g['height'],errors='coerce').notna().sum()),'floors_nonnull':int(pd.to_numeric(g['num_floors'],errors='coerce').notna().sum()) if 'num_floors' in g else 0}
  for res in (1,.5):
   key=f'{res:g}';path=P/(src+'_'+key+'.npy');log('generation',src,key)
   if not path.exists():
    code='''import sys,json,time,resource,numpy as np,geopandas as gpd\nfrom pathlib import Path\nfrom voxcity.generator import get_voxcity\np=Path(sys.argv[1]);src=sys.argv[2];res=float(sys.argv[3]);rect=json.loads(sys.argv[4]);g=gpd.read_file(p/(src+".gpkg"));g=g.set_crs("EPSG:4326") if g.crs is None else g;t=time.monotonic()\nc=get_voxcity(rect,res,building_source=src,building_gdf=g,building_complementary_source="None",land_cover_source="OpenStreetMap",canopy_height_source="Static",dem_source="None",static_tree_height=0,flat_dem=True,gridvis=False,mapvis=False,save_voxcity_data=False,parallel_download=False,output_dir=str(p/(src+"_"+sys.argv[3])))\na=c.voxels.classes;np.save(p/(src+"_"+sys.argv[3]+".npy"),a);print("RESULT_JSON="+json.dumps({"seconds":time.monotonic()-t,"peak_rss_kb":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"shape":a.shape,"height_max":float(np.nanmax(c.buildings.heights))}),flush=True)'''
    (P/'single.py').write_text(code)
    t=time.monotonic();z=subprocess.run(['python',str(P/'single.py'),str(P),src,key,json.dumps(rect)],capture_output=True,text=True,timeout=1800)
    (P/(src+'_'+key+'.log')).write_text(z.stdout+'\nSTDERR\n'+z.stderr[-8000:])
    if z.returncode:raise RuntimeError(f'{src} {key}: {z.returncode}: {z.stderr[-1000:]}')
    d[key+'m']=json.loads(z.stdout.split('RESULT_JSON=')[-1].splitlines()[0]);d[key+'m']['outer_seconds']=time.monotonic()-t
   else:d[key+'m']=json.loads((P/('old_metrics.json' if src=='OpenStreetMap' else 'finish.json')).read_text())['sources'][src][key+'m']
   a=np.load(path,mmap_mode='r');d[key+'m']['file']=dig(path);d[key+'m']['shape']=a.shape
   assert a.shape[:2]==(round(500/res),round(500/res))
   if res==1:
    solid=np.asarray(a[:,:,2]==-3);ii,jj=np.indices((500,500));disk=np.hypot(jj+.5-250,ii+.5-250)<190
    forms={'id':solid,'flip_i':solid[::-1,:],'flip_j':solid[:,::-1],'flip_both':solid[::-1,::-1],'transpose':solid.T,'transpose_flip_i':solid.T[::-1,:],'transpose_flip_j':solid.T[:,::-1],'transpose_flip_both':solid.T[::-1,::-1]}
    d['gate']={k:iou(v,off,disk) for k,v in forms.items()};d['gate_pass']=d['gate']['id']>=.7 and d['gate']['id']>max(v for k,v in d['gate'].items() if k!='id');log('GATE',src,d['gate_pass'],d['gate'])
    if not d['gate_pass']:raise RuntimeError('GATE FAIL '+src+'; no downstream')
  # compact full 3-D fields, each source/res
  for res in (1,.5):
   key=f'{res:g}';a=np.load(P/(src+'_'+key+'.npy'),mmap_mode='r');np.savez_compressed(P/(src+'_'+key+'m.npz'),voxels=a);d[key+'m']['npz']=dig(P/(src+'_'+key+'m.npz'))
 save();log('all gates passed; downstream')
 # Official input & true horizontal slice, prototype units
 for name in ('BD_caseE.stl','RS_caseE.csv','LF_caseE.xls'):
  path=P/name
  if not path.exists():
   r=requests.get('https://zenodo.org/records/15429018/files/'+name+'?download=1',timeout=180);r.raise_for_status();path.write_bytes(r.content)
 mesh=trimesh.load(P/'BD_caseE.stl',force='mesh',process=False);mesh.apply_scale(250)
 section=mesh.section(plane_origin=[0,0,2],plane_normal=[0,0,1]);assert section is not None
 # trimesh section returns line segments; polygonize closed contours instead of projecting roofs
 from shapely.geometry import LineString
 from shapely.ops import polygonize,unary_union
 seg=section.discrete;polys=list(polygonize([LineString(q[:,:2]) for q in seg if len(q)>2]));official=mask(polys)
 if not polys:raise RuntimeError('official section yielded zero closed polygons')
 xy=(np.arange(1640)+.5)*.25-205;xx,yy=np.meshgrid(xy,xy);rad=np.hypot(xx,yy)<200
 D['official']={'triangles':len(mesh.faces),'section_paths':len(seg),'section_polygons':len(polys),'mask_cells':int(official.sum()),'bounds':mesh.bounds.tolist()};save()
 # skeleton narrow segments in official free area, constrain disconnected diagonals by 8-connectivity
 dist=distance_transform_edt(~official)*.25;sk=skeletonize((~official)&rad)&(dist*2<4)
 # only retain length >=10m (8-connected pixel count is approximate arc length)
 groups,num=label(sk,structure=np.ones((3,3),dtype=int));segments=[]
 for n in range(1,num+1):
  pts=np.argwhere(groups==n);length=len(pts)*.25
  if length>=10:segments.append((n,pts,length))
 D['narrow_segments']=len(segments)
 def boundary(a,b):
  aa=np.argwhere(a^binary_erosion(a));bb=np.argwhere(b^binary_erosion(b))
  if len(aa)==0 or len(bb)==0:return None
  return float(np.median(np.r_[cKDTree(bb).query(aa)[0],cKDTree(aa).query(bb)[0]])*.25)
 rs=pd.read_csv(P/'RS_caseE.csv');pt=rs[rs['case']=='ac'].drop_duplicates(['x(m)','y(m)']).copy();assert len(pt)==80
 try:
  sheets=pd.read_excel(P/'LF_caseE.xls',sheet_name=None);D['LF_sheets']={k:{'columns':list(map(str,v.columns)),'head':v.head(18).astype(str).values.tolist()} for k,v in sheets.items()}
 except Exception as ex:D['LF_error']=str(ex)
 rows=[];streets=[]
 for src in ['OpenStreetMap','Overture']:
  log('downstream',src);d=D['sources'][src];a=np.load(P/(src+'_1.npy'),mmap_mode='r');sol=np.asarray(a==-3);v=sol[:,:,2]
  g=gpd.read_file(P/(src+'.gpkg'));g=g.set_crs('EPSG:4326') if g.crs is None else g;up=srcmask(g)
  # 0.25m sampling of 1m solid grids in official coords
  ix=np.clip(np.floor(xx+250).astype(int),0,499);iy=np.clip(np.floor(yy+250).astype(int),0,499)
  vv=v[iy,ix];uu=up[iy,ix];oa=official&rad;va=vv&rad;ua=uu&rad
  d['boundary_voxel_official_m']=boundary(oa,va);d['boundary_upstream_official_m']=boundary(oa,ua)
  dv=distance_transform_edt(~vv)*.25;du=distance_transform_edt(~uu)*.25
  width_err=[];blocked=0
  for sid,pts,length in segments:
   rr,cc=pts.T;ofw=2*dist[rr,cc];vow=2*dv[rr,cc];width_err.extend(abs(ofw-vow).tolist())
   # centerline 2m corridor, same two endpoint zones; connectivity in free VoxCity cells
   corridor=distance_transform_edt(groups!=sid)*.25<=2
   free=corridor&~vv;components,_=label(free,structure=np.ones((3,3),dtype=int))
   e0=components[rr[0],cc[0]];e1=components[rr[-1],cc[-1]];connected=bool(e0 and e0==e1)
   upstream_block=bool(np.any(uu[rr,cc]));blocked+=not connected
   streets.append({'source':src,'segment':sid,'length_m':length,'official_width_m':float(np.median(ofw)),'voxel_width_m':float(np.median(vow)),'connected':connected,'upstream_centerline_blocked':upstream_block,'upstream_width_m':float(np.median(2*du[rr,cc]))})
  d['narrow_width_abs_median_m']=float(np.median(width_err)) if width_err else None;d['narrow_blocked_count']=int(blocked)
  for _,p in pt.iterrows():
   x=float(p['x(m)']);y=float(p['y(m)']);i=int(np.floor(y+250));j=int(np.floor(x+250));r=int(np.floor((y+205)/.25));col=int(np.floor((x+205)/.25))
   rows.append({'source':src,'point_id':p['No.'],'x_m':x,'y_m':y,'voxel':bool(v[i,j]),'official':bool(official[r,col]) if 0<=r<1640 and 0<=col<1640 else False,'upstream':bool(up[i,j])})
  d['points_voxel']=sum(t['voxel'] for t in rows if t['source']==src);d['points_official']=sum(t['official'] for t in rows if t['source']==src);d['points_upstream']=sum(t['upstream'] for t in rows if t['source']==src)
 pd.DataFrame(rows).to_csv(P/'points_v2.csv',index=False);pd.DataFrame(streets).to_csv(P/'streets_v2.csv',index=False)
 # roof component descriptive: horizontal official triangles, now axes true
 faces=np.asarray(mesh.vertices)[mesh.faces];cross=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);horizontal=(np.abs(cross[:,2])/(np.linalg.norm(cross,axis=1)+1e-20)>.9)&(faces[:,:,2].min(axis=1)>.5)
 roof=faces[horizontal];from rasterio.features import rasterize as rz
 from shapely.geometry import Polygon
 roofmask=mask([Polygon(q[:,:2]) for q in roof],.5,205);labs,nlab=label(roofmask)
 desc=[]
 for k in range(1,nlab+1):
  ids=np.argwhere(labs==k)
  if len(ids)<4:continue
  yc,xc=ids.mean(axis=0)*.5-205;zvals=[]
  for q in roof:
   center=q[:,:2].mean(axis=0);i=int((center[1]+205)/.5);j=int((center[0]+205)/.5)
   if 0<=i<820 and 0<=j<820 and labs[i,j]==k:zvals.append(float(q[:,2].mean()))
  if not zvals:continue
  item={'component':k,'x_m':float(xc),'y_m':float(yc),'roof_m':max(zvals),'area_m2':len(ids)*.25}
  for src in ['OpenStreetMap','Overture']:
   a=np.load(P/(src+'_1.npy'),mmap_mode='r');i=int(np.floor(yc+250));j=int(np.floor(xc+250));height=int(np.any(a[i,j,:]==-3))*10 if 0<=i<500 and 0<=j<500 else 0
   item[src+'_height_m']=height;item[src+'_absdiff_m']=abs(item['roof_m']-height)
  desc.append(item)
 pd.DataFrame(desc).to_csv(P/'official_roofs_v2.csv',index=False);D['official_roof_components']=len(desc)
 # exposed cube faces, exact integer boundaries. stream binary STL to avoid giant mesh array
 from itertools import product
 def make_stl(src,res):
  arr=np.load(P/(src+'_'+f'{res:g}'+'.npy'),mmap_mode='r');occ=np.asarray(arr==-3);nx,ny,nz=occ.shape
  path=P/(src+'_'+f'{res:g}'+'m.stl');header=b'VoxCity voxel exposed faces, exact cube boundaries'.ljust(80,b' ')
  import struct
  normal=[(0,0,-1),(0,0,1),(-1,0,0),(1,0,0),(0,-1,0),(0,1,0)]
  templates=[[(0,0,0),(0,1,0),(1,1,0),(1,0,0)],[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],[(0,0,0),(0,0,1),(0,1,1),(0,1,0)],[(1,0,0),(1,1,0),(1,1,1),(1,0,1)],[(0,0,0),(1,0,0),(1,0,1),(0,0,1)],[(0,1,0),(0,1,1),(1,1,1),(1,1,0)]]
  with open(path,'wb') as f:
   f.write(header);f.write(struct.pack('<I',0));cnt=0
   for axis,shift,face in [(2,-1,0),(2,1,1),(0,-1,2),(0,1,3),(1,-1,4),(1,1,5)]:
    near=np.zeros_like(occ);srcsl=[slice(None)]*3;dstsl=[slice(None)]*3
    if shift==-1:srcsl[axis]=slice(0,-1);dstsl[axis]=slice(1,None)
    else:srcsl[axis]=slice(1,None);dstsl[axis]=slice(0,-1)
    near[tuple(dstsl)]=occ[tuple(srcsl)]
    coords=np.argwhere(occ&~near);base=np.array(templates[face],dtype='float32')*res
    n=normal[face]
    for chunk in np.array_split(coords,max(1,(len(coords)+4095)//4096)):
     if not len(chunk):continue
     verts=(chunk[:,None,:]+np.array(templates[face])[None,:,:])*res
     for tri in ((0,1,2),(0,2,3)):
      vtx=verts[:,tri,:].astype('<f4');out=np.empty((len(chunk),50),dtype='u1');out[:,:12]=np.frombuffer(struct.pack('<3f',*n),dtype='u1');out[:,12:48]=vtx.reshape(len(chunk),36).view('u1').reshape(len(chunk),36);out[:,48:]=0;f.write(out.tobytes());cnt+=len(chunk)
   f.seek(80);f.write(struct.pack('<I',cnt))
  return path
 for src in ['OpenStreetMap','Overture']:
  d=D['sources'][src];d['stl']={}
  for res in (1,.5):
   log('stl',src,res);path=make_stl(src,res);info=dig(path);info['faces']=int((info['bytes']-84)//50)
   if res==1:
    mm=trimesh.load(path,force='mesh',process=False);info['bounds']=mm.bounds.tolist();info['watertight']=bool(mm.is_watertight)
    zpath=P/(src+'_1m.stl.zip')
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:z.write(path,arcname=path.name)
    info['zip']=dig(zpath)
   d['stl'][f'{res:g}m']=info;save()
 D['end']=time.time();log('finished')
except Exception as e:
 D['error']=repr(e);D['traceback']=traceback.format_exc();log('ERROR',repr(e))
finally:
 D['end']=time.time();save();(P/'finish3.done').write_text(str(time.time()));print('DONE',D['error'],flush=True)
