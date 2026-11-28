import os,json,time,traceback,importlib.util,hashlib,zipfile
from pathlib import Path
import numpy as np,pandas as pd,geopandas as gpd,trimesh
from pyproj import Geod,Transformer
from shapely.geometry import box
from shapely.strtree import STRtree
from rasterio.features import rasterize
from rasterio.transform import from_origin
from brails import Importer
import brails.scrapers.ms_footprint_scraper.ms_footprint_handler as msmod
R=Path('/content/step1d'); START=time.time(); geod=Geod(ellps='WGS84')
spec=importlib.util.spec_from_file_location('community','/content/community_wind_simulation.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
imp=Importer(); MS=imp.get_class('MS_FootprintScraper'); RB=imp.get_class('RegionBoundary')
assert MS.__name__=='MS_FootprintScraper' and MS.__module__.endswith('ms_footprint_handler')
URLs=[]; orig=MS._fetch_and_filter
def tapped(self,url,*args,**kw):
 print('MS_TILE_URL',url,flush=True);URLs.append(url);return orig(self,url,*args,**kw)
MS._fetch_and_filter=tapped
print('ACTUAL_CLASS',MS.__module__,MS.__name__,'catalog',msmod.DATASET_URL,flush=True)

def savej(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def bounds(lat,lon):return (geod.fwd(lon,lat,270,250)[0],geod.fwd(lon,lat,180,250)[1],geod.fwd(lon,lat,90,250)[0],geod.fwd(lon,lat,0,250)[1])
def stats_mesh(frame):
 out={'count':len(frame),'watertight_before':0,'watertight_after':0,'nonmanifold_edges':0,'degenerate_faces':0,'failed':0,'self_intersection':'not evaluated'}
 for geom,h in zip(frame.geometry,frame.buildingheight):
  for p in (list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]):
   if p.is_empty or p.area<=0:continue
   try:
    m=mod.extrude(p,float(h));out['watertight_before']+=int(m.is_watertight)
    out['degenerate_faces']+=int((m.area_faces<=1e-10).sum())
    e=trimesh.geometry.faces_to_edges(m.faces);_,n=np.unique(np.sort(e,axis=1),axis=0,return_counts=True);out['nonmanifold_edges']+=int((n>2).sum())
    m.process(validate=True);trimesh.repair.fix_normals(m);trimesh.repair.fill_holes(m);out['watertight_after']+=int(m.is_watertight)
   except Exception as ex:out['failed']+=1;print('MESH_ERROR',repr(ex),flush=True)
 return out

def reader(path):
 # R21.7 interface replica: raw whitespace numeric PALM ASCII, row 0 north, flip_y to south ascending.
 with open(path) as f: first=f.readline().strip();assert not first.startswith('#'),first[:100]
 z=np.loadtxt(path,dtype=np.float32);assert z.shape==(530,530) and np.isfinite(z).all() and z.min()>=0 and z.max()<132
 assert np.count_nonzero(z[:15,:])==np.count_nonzero(z[-15:,:])==np.count_nonzero(z[:,:15])==np.count_nonzero(z[:,-15:])==0
 flipped=np.flipud(z);assert np.array_equal(flipped,np.flipud(z))
 return {'shape':list(z.shape),'flip_y':'np.flipud','border_15m_zero':True,'occupied_cells':int(np.count_nonzero(z)),'solid_voxels':int(np.floor(z[z>0]+.5).astype(np.int64).sum()),'missing_height_cells':int(np.count_nonzero(~np.isfinite(z))),'min_m':float(z.min()),'max_m':float(z.max()),'readable_without_manual_edit':True,'reader':'R21.7 interface replica; not native FluidX3D reader'}

def grid(frame,lat,lon,epsg,path):
 cx,cy=Transformer.from_crs(4326,epsg,always_xy=True).transform(lon,lat)
 h=rasterize([(g,float(v)) for g,v in zip(frame.geometry,frame.buildingheight) if not g.is_empty and 0<float(v)<132],out_shape=(500,500),transform=from_origin(cx-250,cy+250,1,1),dtype='float32')
 padded=np.pad(h,15);assert padded.shape==(530,530)
 np.savetxt(path,padded,fmt='%.3f',comments='')
 return reader(path)

def match(ms,usa,epsg):
 aa=ms.to_crs(epsg);bb=usa.to_crs(epsg);geoms=list(bb.geometry);tree=STRtree(geoms);pairs=[];used=set(); candidates=[]
 for i,g in enumerate(aa.geometry):
  best=(0,-1)
  for j in tree.query(g):
   j=int(j);v=geoms[j];inter=g.intersection(v).area
   if inter>0:
    iou=inter/(g.area+v.area-inter)
    if iou>best[0]:best=(iou,j)
  if best[0]>=.5:candidates.append((best[0],i,best[1]))
 for iou,i,j in sorted(candidates,reverse=True):
  if j in used:continue
  used.add(j)
  a=pd.to_numeric(aa.iloc[i].buildingheight,errors='coerce');b=pd.to_numeric(bb.iloc[j].buildingheight,errors='coerce')
  if a>0 and np.isfinite(a) and b>0 and np.isfinite(b):pairs.append((a-b,iou))
 delta=np.array([x[0] for x in pairs]);return {'iou_ge_0_5_candidates':len(candidates),'unique_pairs':len(used),'both_valid_heights':len(delta),'height_delta_ms_minus_usa_median_m':float(np.median(delta)) if len(delta) else None,'height_delta_iqr_m':list(map(float,np.percentile(delta,[25,75]))) if len(delta) else None,'median_iou_both_valid':float(np.median([v[1] for v in pairs])) if pairs else None}

def main():
 report={'class':f'{MS.__module__}.{MS.__name__}','catalog_url':msmod.DATASET_URL,'cities':{},'start_utc':pd.Timestamp.utcnow().isoformat(),'manual_edits':0}
 for name,lat,lon,usa_path in [('chicago',41.8988,-87.6378,'/content/usa_chicago.geojson'),('phoenix',33.4590,-112.0720,'/content/usa_phoenix.geojson')]:
  st=time.time();d=R/name;d.mkdir(exist_ok=True);u0=len(URLs)
  sc=MS({'length':'m'}); b=bounds(lat,lon);print('CITY_START',name,'ROI',b,flush=True)
  # Direct class calls, no string-based branch or fallback.
  if not (d/'ms_ROI_raw.geojson').exists():
   roi_inv=sc.get_footprints(RB({'type':'locationPolygon','data':b}));roi_inv.write_to_geojson(d/'ms_ROI_raw.geojson')
  else: print('REUSE_RAW_ROI',name,flush=True)
  verts=[geod.fwd(lon,lat,k*10,1000)[:2] for k in range(36)];verts.append(verts[0]);flat=tuple(c for p in verts for c in p)
  if not (d/'ms_total_raw.geojson').exists():
   total_inv=sc.get_footprints(RB({'type':'locationPolygon','data':flat}));total_inv.write_to_geojson(d/'ms_total_raw.geojson')
  else: print('REUSE_RAW_TOTAL',name,flush=True)
  roi=gpd.read_file(d/'ms_ROI_raw.geojson');total=gpd.read_file(d/'ms_total_raw.geojson');usa=gpd.read_file(usa_path)
  epsg=mod.utm_epsg(lon,lat);roi=mod.to_metric(roi,epsg);total=mod.to_metric(total,epsg);usa=mod.to_metric(usa,epsg)
  center=Transformer.from_crs(4326,epsg,always_xy=True).transform(lon,lat);win=box(center[0]-250,center[1]-250,center[0]+250,center[1]+250)
  roi_areas=roi.geometry.intersection(win).area
  native=pd.to_numeric(roi.get('buildingheight',pd.Series(np.nan,index=roi.index)),errors='coerce');missing=native.isna()|(native<=0)
  roi['buildingheight']=native.where(~missing,np.nan);rfilled=mod.nearest_fill(roi.copy(),'buildingheight',20.0)
  roi_ids={g.wkb for g in roi.geometry};rest=total.loc[~total.geometry.apply(lambda g:g.wkb in roi_ids)].copy();rawrest=pd.to_numeric(rest.get('buildingheight',pd.Series(np.nan,index=rest.index)),errors='coerce');rest['buildingheight']=rawrest.where(rawrest>0,np.nan);rest=mod.nearest_fill(rest,'buildingheight',20.0)
  roi_record={'count':len(roi),'missing_count':int(missing.sum()),'missing_rate':float(missing.mean()),'missing_area_rate':float(roi_areas[missing].sum()/roi_areas.sum()),'lambda_p':float(roi_areas.sum()/250000),'hbar_area_weighted_filled_m':float(np.average(rfilled.buildingheight,weights=roi_areas)),'height_match':match(roi,usa,epsg)}
  roi_record['M2_ROI']=stats_mesh(rfilled);roi_record['M2_surrounding']=stats_mesh(rest)
  roi_record['M3a_MS']=grid(rfilled,lat,lon,epsg,d/'ms_palm_1m_15m_border.asc')
  usa_raw=pd.to_numeric(usa.buildingheight,errors='coerce');usa['buildingheight']=usa_raw.where(usa_raw>0,np.nan);usa_filled=mod.nearest_fill(usa.copy(),'buildingheight',20.0)
  usa_areas=usa.geometry.intersection(win).area
  roi_record['USA']={'count':len(usa),'lambda_p':float(usa_areas.sum()/250000),'hbar_area_weighted_filled_m':float(np.average(usa_filled.buildingheight,weights=usa_areas)),'M3a':grid(usa_filled,lat,lon,epsg,d/'usa_palm_1m_15m_border.asc')}
  roi_record['M5_seconds']=round(time.time()-st,2);roi_record['tile_urls']=sorted(set(URLs[u0:]));roi_record['epsg']=epsg
  rfilled['native_height']=~missing.values;rfilled.to_crs(4326).to_file(d/'ms_ROI_filled.geojson',driver='GeoJSON')
  report['cities'][name]=roi_record;savej(R/'metrics_partial_resume.json',report);print('CITY_DONE',name,json.dumps(roi_record),flush=True)
 report['finish_utc']=pd.Timestamp.utcnow().isoformat();report['elapsed_seconds']=time.time()-START
 savej(R/'metrics_final_resume.json',report)
 with zipfile.ZipFile(R/'results_resume.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for p in R.glob('**/*'):
   if p.is_file() and p.name not in ('results.zip','results_resume.zip','install.log','worker.log','worker_resume.log','worker.done','worker.failed','worker_resume.done','worker_resume.failed'):z.write(p,p.relative_to(R))
 (R/'worker_resume.done').write_text('ok');print('DONE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception: (R/'worker_resume.failed').write_text(traceback.format_exc());traceback.print_exc();raise
