#!/usr/bin/env python3
"""Independent readback of E2/E3 paired WPS deliveries (no model execution)."""
import collections, datetime as dt, hashlib, json, math, pathlib, struct, sys
import numpy as np
BASE=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
EVENTS={'E2':{'cycles':{'2024051818':6,'2024051718':10,'2024051618':14},'center':(39,-99),'box':(24,53,-123,-75),'end':'2024052000'},'E3':{'cycles':{'2024071218':7,'2024071118':11,'2024071018':15},'center':(44,-92),'box':(29,58,-118,-66),'end':'2024071406'}}
# Count includes t0: E2 6+10+14, E3 7+11+15.
LEVELS=[1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1]
FIVE=('GHT','TT','UU','VV','SPECHUMD')
def read_wps(path,box):
    raw=path.read_bytes();pos=0;fields=[];slabs={}
    lat0,lat1,lon0,lon1=box;nx=int((lon1-lon0)*4)+1;ny=int((lat1-lat0)*4)+1
    while pos<len(raw):
        rec=[]
        for _ in range(5):
            assert pos+8<=len(raw),(path,'truncated')
            n=struct.unpack_from('>I',raw,pos)[0];end=pos+4+n
            assert n<500000000 and end+4<=len(raw) and raw[end:end+4]==raw[pos:pos+4],(path,'framing')
            rec.append(raw[pos+4:end]);pos=end+4
        v,h,proj,wind,data=rec
        assert v==struct.pack('>I',5) and len(h)==156 and len(proj)==28 and len(wind)==4
        assert proj[:8]==b'SWCORNER'
        origin=struct.unpack('>fffff',proj[8:])
        assert origin[:4]==(float(lat0),float(lon0%360),.25,.25),(path,origin)
        lev,rx,ry,iproj=struct.unpack('>fiii',h[140:156])
        assert (rx,ry,iproj)==(nx,ny,0) and len(data)==nx*ny*4,(path,rx,ry,nx,ny)
        assert np.isfinite(np.frombuffer(data,dtype='>f4')).all(),(path,'nonfinite')
        field=h[60:69].decode('ascii').strip();level=int(round(lev));key=(field,level)
        assert key not in slabs,(path,'duplicate',key)
        slabs[key]=hashlib.sha256(data).hexdigest();fields.append(key)
    return fields,slabs,hashlib.sha256(raw).hexdigest(),(ny,nx)
def projection_check(cen,box):
    # WRF d01 spherical Lambert mass grid: 748x600, dx=dy=4km.
    radius=6370000.;phi=math.radians(cen[0]);n=math.sin(phi)
    F=math.cos(phi)*math.tan(math.pi/4+phi/2)**n/n
    rho0=radius*F/math.tan(math.pi/4+phi/2)**n
    coords=[('SW',0,0),('SE',747,0),('NE',747,599),('NW',0,599),('S_mid',373.5,0),('E_mid',747,299.5),('N_mid',373.5,599),('W_mid',0,299.5)]
    points=[]
    for name,ix,iy in coords:
        x=(ix-373.5)*4000.;y=(iy-299.5)*4000.;rho=math.hypot(x,rho0-y)
        lat=math.degrees(2*math.atan((radius*F/rho)**(1/n))-math.pi/2)
        lon=cen[1]+math.degrees(math.atan2(x,rho0-y)/n)
        margin=min(lat-box[0],box[1]-lat,lon-box[2],box[3]-lon)
        assert margin>=3,(name,lat,lon,margin)
        points.append({'point':name,'lat':lat,'lon':lon,'margin_deg':margin})
    return {'points':points,'minimum_margin_deg':min(x['margin_deg'] for x in points),'all_pass':True,'method':'spherical Lambert R=6370000m, nx=748 ny=600 dx=dy=4000m, CEN_LAT=TRUELAT1=TRUELAT2=rounded station latitude, STAND_LON=rounded station longitude'}
def fill_diagnostic(ledger,center):
    radius=6370000.;phi=math.radians(center[0]);n=math.sin(phi)
    F=math.cos(phi)*math.tan(math.pi/4+phi/2)**n/n
    rho0=radius*F/math.tan(math.pi/4+phi/2)**n
    inside=[]
    for item in ledger:
        lat,lon=item['target_lat_lon_east'];lon=((lon+180)%360)-180
        theta=n*math.radians(lon-center[1]);rho=radius*F/math.tan(math.pi/4+math.radians(lat)/2)**n
        x=rho*math.sin(theta);y=rho0-rho*math.cos(theta)
        if abs(x)<=373.5*4000 and abs(y)<=299.5*4000: inside.append(item)
    return {'all_fills':len(ledger),'inside_d01':len(inside),'by_field':dict(collections.Counter(x['field'] for x in inside)),'max_donor_km':max((x['donor_distance_km'] for x in inside),default=None),'over_50km':[x for x in inside if x['donor_distance_km']>50]}
def audit(event):
    conf=EVENTS[event];root=BASE/f'drivers_gc37_{event}_v1';ops=root/f'ops_cpu_{event}_v1'
    assert (ops/f'run_{event.lower()}.exitcode').read_text().strip()=='0'
    report={'event':event,'cycles':{},'d01_coverage':projection_check(conf['center'],conf['box']),'surface_rule':'t0 both arms from GFS f000; future AI own GraphCast T2/U10/V10/PMSL, GFS own same-valid-time forecast; soil/snow/skin/orography/land frozen from same GFS f000; Q2 arm-dependent','pressure_levels_hpa':LEVELS}
    manifest=[];count=0
    for cycle,ntime in conf['cycles'].items():
        entries=json.loads((ops/f'WPS_{cycle}_REPORT.json').read_text())
        assert len(entries)==2*ntime,(cycle,len(entries))
        ledger=json.loads((ops/f'SOIL_FILL_SNOWFIX_{cycle}.json').read_text())
        slots={};start=dt.datetime.strptime(cycle,'%Y%m%d%H');pairs=0
        assert (start+dt.timedelta(hours=6*(ntime-1))).strftime('%Y%m%d%H')==conf['end']
        for item in entries:
            arm=item['arm'];lead=item['lead'];rel=item['file']
            assert arm in ('AI','GFS') and lead in range(0,6*ntime,6) and (arm,lead) not in slots
            assert rel==f'{arm}/{cycle}/FILE:{(start+dt.timedelta(hours=lead)):%Y-%m-%d_%H}'
            fields,slabs,sha,shape=read_wps(root/rel,conf['box'])
            assert len(fields)==172 and item['records']==172 and sha==item['sha256'],rel
            for field in FIVE:
                assert sorted(lev for f,lev in fields if f==field and lev<200000)==sorted(x*100 for x in LEVELS),(rel,field)
            assert all(f!='PSFC' for f,lev in fields)
            slots[(arm,lead)]=slabs;manifest.append(f'{sha}  {rel}');count+=1
        for lead in range(0,6*ntime,6):
            ai=slots[('AI',lead)];gfs=slots[('GFS',lead)]
            shared={k:v for k,v in ai.items() if k[1]>=200000 and k[0] not in ('PMSL','SPECHUMD','TT','UU','VV')}
            assert len(shared)==12 and shared=={k:v for k,v in gfs.items() if k in shared},(cycle,lead,'shared_surface')
            for field in ('TT','UU','VV'):
                k=(field,200100)
                assert (ai[k]==gfs[k]) == (lead==0),(cycle,lead,field,'near_surface_source')
            if lead==0:assert ai[('PMSL',201300)]==gfs[('PMSL',201300)]
            pairs+=1
        report['cycles'][cycle]={'files':len(entries),'times_per_arm':ntime,'grid_shape':shape,'five_fields_31_levels_finite':True,'shared_surface_fields':12,'shared_surface_byte_equal_pairs':pairs,'fill_ledger':str(ops/f'SOIL_FILL_SNOWFIX_{cycle}.json'),'fill_d01':fill_diagnostic(ledger,conf['center']),'build_report':str(ops/f'WPS_{cycle}_REPORT.json')}
    assert count==sum(2*n for n in conf['cycles'].values())
    report['total_files']=count;report['all_valid']=True
    dest=ops/f'READBACK_GC37_{event}_V1.json';sums=root/'SHA256SUMS'
    assert not dest.exists() and not sums.exists(),(dest,sums)
    with dest.open('x') as f:json.dump(report,f,indent=2)
    with sums.open('x') as f:f.write('\n'.join(sorted(manifest))+'\n')
    print(json.dumps({'event':event,'readback_report':str(dest),'sha256sums':str(sums),'files':count,'d01_min_margin':report['d01_coverage']['minimum_margin_deg']},indent=2))
if __name__=='__main__':
    for e in sys.argv[1:]:audit(e)
