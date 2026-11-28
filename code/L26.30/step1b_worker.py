import json, time, sys, importlib.util, traceback, math
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, trimesh
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pyproj import Geod, Transformer
from shapely.geometry import box
from rasterio.features import rasterize
from rasterio.transform import from_origin
from brails import Importer
R=Path('/content/qtl_l2630_step1b'); R.mkdir(exist_ok=True)
ORIG=Path('/content/qtl_l2630_step1a/selected')
modpath=ORIG/'community_wind_simulation.py'; spec=importlib.util.spec_from_file_location('community',modpath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
imp=Importer(); RB=imp.get_class('RegionBoundary'); geod=Geod(ellps='WGS84')
metrics={'started_utc':pd.Timestamp.utcnow().isoformat(),'sources':{},'city':'Detroit Midtown','manual_building_edits':0}
def log(*x): print(pd.Timestamp.utcnow().isoformat(),*x,flush=True)
def bounds(lat,lon):
 return (geod.fwd(lon,lat,270,250)[0],geod.fwd(lon,lat,180,250)[1],geod.fwd(lon,lat,90,250)[0],geod.fwd(lon,lat,0,250)[1])
def scrape(lat,lon,tag):
 d=R/tag;d.mkdir(exist_ok=False)
 b=bounds(lat,lon);rb=RB({'type':'locationPolygon','data':b});cls='MS_FootprintScraper' if tag=='MS' else 'USA_FootprintScraper';sc=imp.get_class(cls)({'length':'m'})
 t=time.time();log('FETCH',tag,b); inv=sc.get_footprints(rb);inv.write_to_geojson(d/'inventoryROI.geojson');roi=gpd.read_file(d/'inventoryROI.geojson');log('FETCH_DONE',tag,len(roi),time.time()-t)
 verts=[geod.fwd(lon,lat,i*10,1000)[:2] for i in range(36)];verts.append(verts[0]);flat=tuple(c for p in verts for c in p)
 whole=sc.get_footprints(RB({'type':'locationPolygon','data':flat}));whole.write_to_geojson(d/'inventoryTotal.geojson');log('TOTAL_DONE',tag,time.time()-t)
 return d,roi,gpd.read_file(d/'inventoryTotal.geojson'),t
# use a fresh child root for every source; no overwriting
try:
 for city,lat,lon in [('Detroit Midtown',42.3550,-83.0640),('Phoenix Roosevelt',33.4590,-112.0720)]:
  citykey='detroit' if city.startswith('Detroit') else 'phoenix'
  results={}
  for short in ('MS','USA'):
   tag=citykey+'_'+short
   try:
    d,roi,total,start=scrape(lat,lon,tag)
    epsg=mod.utm_epsg(lon,lat); roi=mod.to_metric(roi,epsg);total=mod.to_metric(total,epsg)
    ids={x.wkb for x in roi.geometry};rest=total.loc[~total.geometry.apply(lambda x:x.wkb in ids)].copy()
    ctr=Transformer.from_crs(4326,epsg,always_xy=True).transform(lon,lat);xmin=ctr[0]-250;ymax=ctr[1]+250;window=box(ctr[0]-250,ctr[1]-250,ctr[0]+250,ctr[1]+250)
    a=roi.geometry.intersection(window).area; plan=float(a.sum()/250000)
    raw=pd.to_numeric(roi.get('buildingheight',pd.Series(np.nan,index=roi.index)),errors='coerce');valid=raw.notna()&(raw>0)
    # hbar area-weighted by occupied ground area; explicit source-imputation estimate
    roi['buildingheight']=raw.where(valid,np.nan)
    rfill=mod.nearest_fill(roi.copy(),'buildingheight',20.0)
    mean=float(np.average(rfill['buildingheight'],weights=np.maximum(a,1e-9))) if a.sum()>0 else None
    results[short]={'count':len(roi),'native_count':int(valid.sum()),'missing_count':int((~valid).sum()),'missing_count_rate':float((~valid).mean()) if len(roi) else None,'missing_area_rate':float(a[~valid].sum()/a.sum()) if a.sum() else None,'lambda_p':plan,'hbar_area_weighted_filled_m':mean,'three_hbar_m':3*mean if mean else None,'epsg':epsg}
    if citykey=='detroit' and short=='USA' and not(0.12<=plan<=0.26 and 10<=mean<=25 and 3*mean<=130.5):log('DETROIT_THRESHOLD_FAIL_USA',results[short])
    for label,frame in (('ROI',roi),('Surrounding',rest)):
     frame=frame.copy();rr=pd.to_numeric(frame.get('buildingheight',pd.Series(np.nan,index=frame.index)),errors='coerce');missing=rr.isna()|(rr<=0);frame['native_height']=~missing;frame['buildingheight']=rr.where(~missing,np.nan);frame=mod.nearest_fill(frame,'buildingheight',20.0)
     frame['data_source']='Microsoft Global ML Building Footprints' if short=='MS' else 'FEMA USA Structures';frame['license']='ODbL 1.0' if short=='MS' else 'CC BY 4.0';frame['retrieved_utc']=pd.Timestamp.utcnow().isoformat()
     frame.to_crs(4326).to_file(d/(label+'_heights.geojson'),driver='GeoJSON')
     parts=[];before=[];after=[];nonman=0;deg=0
     for geom,h in zip(frame.geometry,frame.buildingheight):
      polys=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
      for p in polys:
       if p.is_empty or p.area<=0:continue
       try:
        m=mod.extrude(p,float(h));before.append(bool(m.is_watertight));deg+=int((m.area_faces<=1e-10).sum());e=trimesh.geometry.faces_to_edges(m.faces);_,n=np.unique(np.sort(e,axis=1),axis=0,return_counts=True);nonman+=int((n>2).sum());m.process(validate=True);trimesh.repair.fix_normals(m);trimesh.repair.fill_holes(m);after.append(bool(m.is_watertight));parts.append(m)
       except Exception as ex:log('EXTRUDE_FAIL',tag,label,str(ex));before.append(False);after.append(False)
     if parts:mod.write_stl_ascii(trimesh.util.concatenate(parts),d/(label+'.stl'),label)
     results[short][label]={'count':len(frame),'missing_count':int(missing.sum()),'missing_area_rate':float(frame.geometry.area[missing].sum()/frame.geometry.area.sum()) if frame.geometry.area.sum()>0 else None,'watertight_before':sum(before),'watertight_after':sum(after),'mesh_count':len(before),'nonmanifold_edges':nonman,'degenerate_faces':deg,'self_intersections':'not evaluated'}
     fig,ax=plt.subplots(figsize=(7,7));frame.plot(ax=ax,column='native_height',categorical=True,legend=True,edgecolor='black',linewidth=.15);ax.set_aspect('equal');ax.set_title(f'{city} {short} {label} native/fill | source: '+frame['data_source'].iloc[0]);fig.tight_layout();fig.savefig(d/(label+'_footprints.png'),dpi=140);plt.close(fig)
    # R21.7 1-m grid, north-to-south ASCII flip_y; cell-centre polygon rasterization
    shapes=[(geom,float(h)) for geom,h in zip(rfill.geometry,rfill.buildingheight) if not geom.is_empty and np.isfinite(h) and h>0]
    height=rasterize(shapes,out_shape=(500,500),transform=from_origin(xmin,ymax,1,1),fill=0,dtype='float32',all_touched=False)
    if height.max()>=132:raise ValueError('height >= 132m')
    # j=0 at northern edge in file; flip_y at consumer converts to physical y increasing
    np.savetxt(d/'palm_height_1m.asc',height,fmt='%.3f',header='PALM ASCII 2.5D; 500 rows north-to-south x 500 columns east; dx=dy=1 m; flip_y on import; x=UTM east (assumed wind direction); periodic horizontal',comments='# ')
    counts=np.floor(height[height>0]+0.5).astype(int);solid=int(counts.sum());occupied=int(np.count_nonzero(height));raster_area=occupied;polygon_area=float(a.sum());ratio=float(raster_area/polygon_area) if polygon_area else None
    results[short]['M3a']={'grid_shape':[500,500],'dx_m':1,'height_min':float(height.min()),'height_max':float(height.max()),'occupied_cells':occupied,'solid_voxels':solid,'footprint_area_polygon_m2':polygon_area,'occupied_area_raster_m2':raster_area,'area_ratio':ratio,'missing_height_cells':int(np.count_nonzero((height>0)&(~np.isfinite(height)))),'flip_y':'file row 0 north, consumer flip_y to ascending y','x_alignment':'UTM east; wind direction not established; cannot certify x along inflow','horizontal_periodic':'boundary flag to be set in R21.7; format-only self-check','manual_edits':0}
    fig,ax=plt.subplots(figsize=(7,7));im=ax.imshow(height,origin='upper',extent=(xmin,xmin+500,ymax-500,ymax));fig.colorbar(im,ax=ax,label='height [m]');ax.set_title(f'{city} {short} 1 m height | source: '+rfill.get('data_source',pd.Series(['source'])).iloc[0]);fig.tight_layout();fig.savefig(d/'height_grid.png',dpi=150);plt.close(fig)
    for f in d.iterdir():
     if f.suffix in ('.geojson','.stl','.asc','.png'):(d/(f.name+'.license.json')).write_text(json.dumps({'data_source':'Microsoft Global ML Building Footprints' if short=='MS' else 'FEMA USA Structures','license':'ODbL 1.0' if short=='MS' else 'CC BY 4.0','retrieved_utc':pd.Timestamp.utcnow().isoformat(),'file':f.name},indent=2))
    results[short]['seconds']=round(time.time()-start,1);log('SOURCE_DONE',tag,results[short]);(R/'metrics_partial.json').write_text(json.dumps(metrics|{'city_results':results},indent=2))
   except Exception as e:results[short]={'error':repr(e)};log('SOURCE_ERROR',tag,traceback.format_exc());(R/'metrics_partial.json').write_text(json.dumps(metrics|{'city_results':results},indent=2))
  metrics['sources'][citykey]=results
  if citykey=='detroit':
   vals=[x for x in results.values() if 'lambda_p' in x]
   if vals and all(0.12<=x['lambda_p']<=0.26 and 10<=x['hbar_area_weighted_filled_m']<=25 and x['three_hbar_m']<=130.5 for x in vals):break
 metrics['finished_utc']=pd.Timestamp.utcnow().isoformat();(R/'metrics_final.json').write_text(json.dumps(metrics,indent=2));(R/'worker.done').write_text('ok');log('DONE')
except Exception:
 (R/'worker.failed').write_text(traceback.format_exc());log(traceback.format_exc());raise
