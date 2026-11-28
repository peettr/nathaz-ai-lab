#!/usr/bin/env python3
"""Independent WPS readback, paired slab comparison and d01 coverage."""
import sys, json, hashlib, datetime as dt, pathlib, struct, collections
import numpy as np
from pyproj import CRS, Transformer
from wps_format5 import read_records, readback
P=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
LEVELS=[1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1]
FIVE={'GHT','TT','UU','VV','SPECHUMD'}
SHARED={'SOILHGT','LANDSEA','SKINTEMP','SNOW'}|{'ST'+x for x in ('000010','010040','040100','100200')}|{'SM'+x for x in ('000010','010040','040100','100200')}
assert len(SHARED)==12

def records(path):
    it=iter(read_records(path));out={};grid=None
    while True:
        try: vers=next(it)
        except StopIteration: break
        assert vers==struct.pack('>I',5)
        hdr,proj,wind,slab=[next(it) for _ in range(4)]
        assert len(hdr)==156 and len(proj)==28 and len(wind)==4
        field=hdr[60:69].decode().strip();level,nx,ny,iproj=struct.unpack('>fiii',hdr[140:156]);level=int(round(level))
        assert iproj==0 and len(slab)==nx*ny*4
        lat,lon,dlat,dlon,radius=struct.unpack('>fffff',proj[8:28]);assert proj[:8]==b'SWCORNER'
        coord=(lat,lon,dlat,dlon,nx,ny)
        if grid is None:grid=coord
        assert grid==coord
        key=(field,level)
        assert key not in out,key
        arr=np.frombuffer(slab,dtype='>f4')
        assert np.isfinite(arr).all(),key
        out[key]=slab if field in SHARED and level==200100 else None
    assert len(out)==172,len(out)
    for field in FIVE:
        assert sorted(lev for f,lev in out if f==field and lev<200000)==sorted(x*100 for x in LEVELS),field
    assert {(f,l) for f,l in out if f in SHARED}=={(f,200100) for f in SHARED}
    return out,grid

def coverage(domain,grid):
    lat0,lon0,dlat,dlon,nx,ny=grid
    lo=lon0 if lon0<=180 else lon0-360;hi=lo+(nx-1)*dlon
    south=lat0;north=lat0+(ny-1)*dlat
    clat=float(domain['cen_lat']);clon=float(domain['cen_lon'])
    sphere=CRS.from_proj4(f'+proj=lcc +lat_1={clat} +lat_2={clat} +lat_0={clat} +lon_0={clon} +R=6371229 +units=m +no_defs')
    inv=Transformer.from_crs(sphere,CRS.from_epsg(4326),always_xy=True)
    # 748x600 at 4 km, center of each corner cell (equivalent to WRF center coordinates).
    halfx=(748-1)*4000/2;halfy=(600-1)*4000/2
    pts={name:(x,y) for name,x,y in [('SW',-halfx,-halfy),('SE',halfx,-halfy),('NE',halfx,halfy),('NW',-halfx,halfy),('S',0,-halfy),('E',halfx,0),('N',0,halfy),('W',-halfx,0)]}
    result=[]
    for name,(x,y) in pts.items():
        lon,lat=inv.transform(x,y);margin=min(lat-south,north-lat,lon-lo,hi-lon)
        result.append({'point':name,'lat':lat,'lon':lon,'margin_deg':margin})
    assert min(p['margin_deg'] for p in result)>=3, result
    return {'grid':list(grid),'points':result,'minimum_margin_deg':min(p['margin_deg'] for p in result)}

def main(event):
    root=P/f'drivers_{event}_v1';cfg=json.loads((P/'inputs_N1N3N4_v1'/'event_times_bbox_gc37x.json').read_text())['events'][event]
    results={};entries=[];grids=[]
    for lead in (24,48,72):
        cycle=dt.datetime.fromisoformat(cfg['leads'][f'{lead}h']['t0']).strftime('%Y%m%d%H')
        n=int(cfg['leads'][f'{lead}h']['length_h']//6)+1
        ai=sorted((root/'AI'/cycle).glob('FILE:*'));gfs=sorted((root/'GFS'/cycle).glob('FILE:*'))
        assert len(ai)==len(gfs)==n,(event,cycle,len(ai),len(gfs),n)
        assert [p.name for p in ai]==[p.name for p in gfs]
        pairs=[]
        for a,g in zip(ai,gfs):
            ar,ag=records(a);gr,gg=records(g);assert ag==gg
            grids.append(ag)
            assert all(ar[(f,200100)]==gr[(f,200100)] for f in SHARED)
            if a.name==f'FILE:{dt.datetime.strptime(cycle,"%Y%m%d%H"):%Y-%m-%d_%H}':
                assert a.read_bytes()==g.read_bytes(),'t0 not identical'
            ah=readback(a)['sha256'];gh=readback(g)['sha256']
            entries.extend([(ah,str(a.relative_to(root))),(gh,str(g.relative_to(root)))])
            pairs.append({'time':a.name,'shared_surface_byte_equal':True,'t0_identical':a.name==f'FILE:{dt.datetime.strptime(cycle,"%Y%m%d%H"):%Y-%m-%d_%H}'})
        soil=root/f'ops_{event}_{lead}h_GFS_b1'/f'SOIL_FILL_SNOWFIX_{cycle}.json'
        fills=json.loads(soil.read_text()) if soil.exists() else None
        assert fills is not None
        results[cycle]={'pairs':n,'files':2*n,'five_fields_31_levels_finite':True,'shared_surface_fields':sorted(SHARED),'shared_byte_equal_pairs':n,'t0_identical':True,'near_surface_future':'AI GraphCast; GFS native forecast','fill_ledger':str(soil),'fill_count':len(fills),'pairs_detail':pairs}
    assert len(set(grids))==1
    cov=coverage(cfg['domain'],grids[0])
    report={'event':event,'cycles':results,'d01_coverage':cov,'files':len(entries),'sha256_manifest':str(root/'SHA256SUMS')}
    out=root/f'READBACK_GC37X_{event}_V1.json'
    if out.exists() or (root/'SHA256SUMS').exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2))
    (root/'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for h,name in sorted(entries,key=lambda x:x[1])))
    print(json.dumps({'event':event,'report':str(out),'files':len(entries),'min_margin':cov['minimum_margin_deg'],'fills':[x['fill_count'] for x in results.values()]},ensure_ascii=False),flush=True)
if __name__=='__main__':main(sys.argv[1])
