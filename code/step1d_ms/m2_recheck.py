from pathlib import Path
import json, numpy as np, pandas as pd, geopandas as gpd, trimesh
from brails import Importer
import importlib.util
R=Path('/content/step1d')
spec=importlib.util.spec_from_file_location('community','/content/community_wind_simulation.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
report={}
for city,lat,lon in [('chicago',41.8988,-87.6378),('phoenix',33.4590,-112.0720)]:
    epsg=mod.utm_epsg(lon,lat); d=R/city; report[city]={}
    for label,path in [('roi',d/'ms_ROI_filled.geojson'),('total',d/'ms_total_raw.geojson')]:
        g=mod.to_metric(gpd.read_file(path),epsg)
        native=pd.to_numeric(g.buildingheight,errors='coerce');g['buildingheight']=native.where(native>0,np.nan)
        g=mod.nearest_fill(g,'buildingheight',20.0)
        count=0; pre=post=nonmanifold=degenerate=failed=0; errors=[]
        for geom,h in zip(g.geometry,g.buildingheight):
            for poly in (list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]):
                if poly.is_empty or poly.area<=0:continue
                count+=1
                try:
                    m=mod.extrude(poly,float(h));pre+=bool(m.is_watertight)
                    degenerate+=int((m.area_faces<=1e-10).sum())
                    e=trimesh.geometry.faces_to_edges(m.faces);_,n=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
                    nonmanifold+=int((n>2).sum());m.process(validate=True);trimesh.repair.fix_normals(m);trimesh.repair.fill_holes(m);post+=bool(m.is_watertight)
                except Exception as ex:
                    failed+=1
                    if len(errors)<3:errors.append(repr(ex))
        report[city][label]={'pieces':count,'watertight_before':pre,'watertight_after':post,'nonmanifold_edges':nonmanifold,'degenerate_faces':degenerate,'failed':failed,'errors':errors,'self_intersection':'not evaluated'}
        print(city,label,report[city][label],flush=True)
(R/'m2_recheck.json').write_text(json.dumps(report,indent=2))
