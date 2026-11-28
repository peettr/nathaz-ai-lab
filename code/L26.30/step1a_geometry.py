import json,time,math,sys,urllib.request,importlib.util,traceback
from pathlib import Path
import numpy as np,pandas as pd,geopandas as gpd,trimesh
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Polygon,box
from pyproj import Geod
from brails import Importer
R=Path('/content/qtl_l2630_step1a'); t0=time.time(); log=lambda *a:print(time.strftime('%Y-%m-%d %H:%M:%S'),*a,flush=True)
try:
 cand=json.loads((R/'candidates.json').read_text()); good={k:v for k,v in cand.items() if v.get('coverage') is not None}; assert len(good)>=2,good
 name,choice=max(good.items(),key=lambda kv:(kv[1]['coverage'],kv[1]['count']))
 lat,lon={'Detroit Midtown':(42.3550,-83.0640),'Philadelphia Center City':(39.9526,-75.1636),'Chicago Near North':(41.8988,-87.6378)}[name]
 out=R/'selected';out.mkdir(exist_ok=False);geod=Geod(ellps='WGS84'); log('selected',name,choice)
 src='https://raw.githubusercontent.com/NHERI-SimCenter/SimCenterBackendApplications/935d0961ccca/modules/createEVENT/advancedCFDWithBRAILS/community_wind_simulation.py'
 source=out/'community_wind_simulation.py';source.write_bytes(urllib.request.urlopen(src,timeout=30).read())
 spec=importlib.util.spec_from_file_location('community',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 imp=Importer();RB=imp.get_class('RegionBoundary');Scraper=imp.get_class('USA_FootprintScraper');scraper=Scraper({'length':'m'})
 verts=[geod.fwd(lon,lat,i*10,1000)[:2] for i in range(36)];verts.append(verts[0]);flat=tuple(c for p in verts for c in p)
 total=scraper.get_footprints(RB({'type':'locationPolygon','data':flat}));full=out/'inventoryTotal.geojson';total.write_to_geojson(full)
 roi=out/'inventoryROI.geojson';roi.write_bytes(Path(choice['file']).read_bytes())
 g=gpd.read_file(full); r=gpd.read_file(roi);assert len(g)>len(r)>0,(len(g),len(r))
 # same CRS / rotation zero as community step 2; exclude exact ROI geometries from larger source
 epsg=mod.utm_epsg(lon,lat);g=mod.to_metric(g,epsg);r=mod.to_metric(r,epsg)
 roi_ids={v.wkb for v in r.geometry};rest=g.loc[~g.geometry.apply(lambda v:v.wkb in roi_ids)].copy();assert len(rest)>0
 metrics={'selected':name,'candidate_coverage':cand,'counts':{'roi':len(r),'surrounding':len(rest)},'src':src,'crs':f'EPSG:{epsg}','start_epoch':t0,'manual_edits':0,'snappy':'not run (OpenFOAM v2506 unavailable until Step 2)'}
 all_poly=[]
 for tag,frame in [('ROI',r),('Surrounding',rest)]:
  frame=frame.copy();frame['buildingheight']=pd.to_numeric(frame.get('buildingheight',pd.Series(np.nan,index=frame.index)),errors='coerce')
  missing=frame['buildingheight'].isna()|(frame['buildingheight']<=0)
  frame['native_height']=~missing; areas=frame.geometry.area; metrics[tag]={'buildings':len(frame),'missing_count':int(missing.sum()),'missing_count_rate':float(missing.mean()),'missing_area_rate':float(areas[missing].sum()/areas.sum()),'area_m2':float(areas.sum())}
  frame.loc[missing,'buildingheight']=np.nan
  frame=mod.nearest_fill(frame,'buildingheight',20.0)
  frame['source']='FEMA USA Structures';frame['license']='US federal government public-domain candidate; verify ArcGIS metadata';frame['retrieved_at_utc']=pd.Timestamp.utcnow().isoformat()
  file=out/(tag+'_heights.geojson');frame.to_crs(4326).to_file(file,driver='GeoJSON')
  all_poly.extend(list(zip(frame.geometry,frame['buildingheight'])))
  parts=[];building_w=[];repair_w=[];deg=0;nonman=0;faces=0
  for geom,h in zip(frame.geometry,frame['buildingheight']):
   polys=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
   for p in polys:
    if p.is_empty or p.area<=0:continue
    try:
     m=mod.extrude(p,float(h));building_w.append(bool(m.is_watertight))
     zero=(m.area_faces<=1e-10);deg+=int(zero.sum());e=trimesh.geometry.faces_to_edges(m.faces);_,n=np.unique(np.sort(e,axis=1),axis=0,return_counts=True);nonman+=int((n>2).sum())
     m.process(validate=True);trimesh.repair.fix_normals(m);trimesh.repair.fill_holes(m);repair_w.append(bool(m.is_watertight));parts.append(m);faces+=len(m.faces)
    except Exception as exc: log('mesh fail',tag,repr(exc));building_w.append(False);repair_w.append(False)
  assert parts,tag
  combined=trimesh.util.concatenate(parts)
  target=out/(tag+'.stl');mod.write_stl_ascii(combined,target,tag)
  metrics[tag].update({'watertight_before_count':sum(building_w),'watertight_before_den':len(building_w),'watertight_after_count':sum(repair_w),'watertight_after_den':len(repair_w),'watertight_combined_after':bool(combined.is_watertight),'nonmanifold_edges_before':nonman,'degenerate_faces_before':deg,'faces_after':faces,'self_intersections':'not evaluated (trimesh lacks robust built-in triangle self-intersection test)'})
  plt.figure(figsize=(7,7));frame.plot(ax=plt.gca(),column='native_height',categorical=True,legend=True,edgecolor='k',linewidth=.15);plt.axis('equal');plt.title(f'{tag}: native height vs filled | USA Structures');plt.xlabel('UTM x [m]');plt.ylabel('UTM y [m]');plt.tight_layout();plt.savefig(out/(tag+'_footprints.png'),dpi=160);plt.close()
  fig=plt.figure(figsize=(7,6));ax=fig.add_subplot(projection='3d');
  for mesh in parts[:250]:
   c=mesh.centroid;ax.scatter(c[0],c[1],c[2],s=3,color='#4083ba')
  ax.set(xlabel='UTM x [m]',ylabel='UTM y [m]',zlabel='height [m]',title=f'{tag} geometry, centroid preview');fig.tight_layout();fig.savefig(out/(tag+'_3d.png'),dpi=150);plt.close(fig)
  for pth in [target,file,out/(tag+'_footprints.png'),out/(tag+'_3d.png')]:
   (out/(pth.name+'.source.json')).write_text(json.dumps({'data_source':'FEMA USA Structures via BRAILS++','license':'US federal public-domain candidate; metadata verification pending','retrieved_at_utc':pd.Timestamp.utcnow().isoformat(),'parent':pth.name},indent=2))
 metrics['elapsed_seconds']=round(time.time()-t0,1)
 (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2));log('DONE',json.dumps(metrics,ensure_ascii=False));(R/'geometry.done').write_text('ok')
except Exception:
 log(traceback.format_exc());(R/'geometry.failed').write_text(traceback.format_exc());raise
