#!/usr/bin/env python3
"""Independent CRC WPS framing/field-byte readback; no driver mutation."""
import collections
import datetime as dt
import hashlib
import json
import pathlib
import struct
import math
import sys

ROOT=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/drivers_gc37_v2')
OPS=ROOT/'ops_cpu_v2'
LEVELS=[int(x) for x in (OPS/'COMMON_LEVELS.txt').read_text().strip().split(',')]
CYCLES={'2020060806':6,'2020060706':10,'2020060606':14}
FIELDS={'GHT','TT','UU','VV','SPECHUMD'}

def wps(path):
    raw=path.read_bytes(); pos=0; out=[]; chunks={}
    while pos<len(raw):
        rec=[]
        for _ in range(5):
            assert pos+8<=len(raw),(path,'trunc')
            n=struct.unpack_from('>I',raw,pos)[0]
            assert n<500000000,(path,n)
            end=pos+4+n
            assert end+4<=len(raw) and raw[end:end+4]==raw[pos:pos+4],(path,'framing')
            rec.append(raw[pos+4:end]);pos=end+4
        v,h,proj,wind,data=rec
        assert v==struct.pack('>I',5) and len(h)==156 and len(proj)==28 and len(wind)==4
        assert proj[:8]==b'SWCORNER'
        assert struct.unpack('>fffff',proj[8:])[:4]==(20.0,230.0,0.25,0.25),(path,'wrong_grid_origin')
        lev,nx,ny,iproj=struct.unpack('>fiii',h[140:156])
        assert iproj==0 and (nx,ny)==(241,141) and len(data)==nx*ny*4,(path,nx,ny)
        import numpy as np
        vals=np.frombuffer(data,dtype='>f4')
        assert np.isfinite(vals).all(),(path,'nonfinite')
        field=h[60:69].decode('ascii').strip();level=int(round(lev))
        out.append((field,level))
        if level>=200000 and field not in ('PMSL','SPECHUMD'):
            key=(field,level)
            assert key not in chunks,(path,key)
            chunks[key]=hashlib.sha256(data).hexdigest()
    assert pos==len(raw)
    return out,chunks,hashlib.sha256(raw).hexdigest()

def domain_coverage():
    """Inverse spherical Lambert conformal on the WRF mass grid."""
    radius=6370000.; center_lon=-100.; phi=math.radians(38.)
    n=math.sin(phi); F=math.cos(phi)*math.tan(math.pi/4+phi/2)**n/n
    rho0=radius*F/math.tan(math.pi/4+phi/2)**n
    points=[('SW',0,0),('SE',747,0),('NE',747,599),('NW',0,599),
            ('S_mid',373.5,0),('E_mid',747,299.5),('N_mid',373.5,599),('W_mid',0,299.5)]
    result=[]
    for label,ix,iy in points:
        x=(ix-373.5)*4000.;y=(iy-299.5)*4000.
        rho=math.hypot(x,rho0-y)
        lat=math.degrees(2*math.atan((radius*F/rho)**(1/n))-math.pi/2)
        lon=center_lon+math.degrees(math.atan2(x,rho0-y)/n)
        margin=min(lat-20,55-lat,lon+130,-70-lon)
        assert margin>=3,(label,lat,lon,margin)
        result.append({'point':label,'lat_deg':lat,'lon_deg_west_negative':lon,'nearest_edge_margin_deg':margin})
    return {'projection':'spherical Lambert conformal, CEN_LAT=TRUELAT1=TRUELAT2=38, STAND_LON=-100, dx=dy=4000m, nx=748, ny=600, center indices=(373.5,299.5), sphere radius=6370000m',
            'driver_box':'20..55 N, 230..290 E','min_required_margin_deg':3,
            'all_points_pass':True,'corners_and_edge_midpoints':result}

def fill_d01_diagnostic(ledger):
    """Project filled-cell centers into the declared WRF d01 mass-grid rectangle."""
    radius=6370000.; phi=math.radians(38.); n=math.sin(phi)
    F=math.cos(phi)*math.tan(math.pi/4+phi/2)**n/n
    rho0=radius*F/math.tan(math.pi/4+phi/2)**n
    inside=[]; byfield=collections.Counter(); far=[]
    for row in ledger:
        lat,lon=row['target_lat_lon_east']; lon=((lon+180)%360)-180
        theta=n*math.radians(lon+100)
        rho=radius*F/math.tan(math.pi/4+math.radians(lat)/2)**n
        x=rho*math.sin(theta); y=rho0-rho*math.cos(theta)
        if abs(x)<=(747/2)*4000 and abs(y)<=(599/2)*4000:
            inside.append(row); byfield[row['field']]+=1
            if row['donor_distance_km']>50:
                far.append({'field':row['field'],'target_lat_lon_east':row['target_lat_lon_east'],
                    'donor_lat_lon_east':row['donor_lat_lon_east'],
                    'donor_distance_km':row['donor_distance_km'],'filled_value':row['filled_value']})
    return {'criterion':'fill target cell center inside inclusive d01 Lambert mass-grid rectangle; donor distance is source ledger great-circle km',
        'all_fills':len(ledger),'inside_d01_count':len(inside),'inside_d01_by_field':dict(sorted(byfield.items())),
        'inside_d01_max_donor_distance_km':max((r['donor_distance_km'] for r in inside),default=None),
        'inside_d01_over_50km_count':len(far),'inside_d01_over_50km':far}

def main():
    assert (OPS/'run.exitcode').read_text().strip()=='0'
    result={'cycles':{},'d01_coverage':domain_coverage(),'shared_surface_field_rule':'all level>=200000 except PMSL and SPECHUMD (Q2) compared as exact binary slabs','readback':'WPS format-5 Fortran framing, 241x141 grids, all finite; five high-air fields at each of 31 levels'}
    manifest=[]; all_pairs=0; fills={}
    for cycle,n in CYCLES.items():
        entries=json.loads((OPS/f'WPS_{cycle}_REPORT.json').read_text())
        assert len(entries)==2*n,(cycle,len(entries))
        ledger=json.loads((OPS/f'SOIL_FILL_SNOWFIX_{cycle}.json').read_text())
        fill_counts=dict(collections.Counter(x['field'] for x in ledger))
        assert all('target_lat_lon_east' in x and 'donor_lat_lon_east' in x and 'filled_value' in x for x in ledger)
        fills[cycle]=fill_counts
        fill_d01=fill_d01_diagnostic(ledger)
        start=dt.datetime.strptime(cycle,'%Y%m%d%H')
        assert (start+dt.timedelta(hours=(n-1)*6)).strftime('%Y%m%d%H')=='2020060912'
        step_results={}; seen=set()
        for entry in entries:
            arm=entry['arm'];lead=entry['lead'];rel=entry['file']
            assert arm in ('AI','GFS') and lead in range(0,n*6,6) and (arm,lead) not in seen
            seen.add((arm,lead))
            assert rel==f'{arm}/{cycle}/FILE:{(start+dt.timedelta(hours=lead)):%Y-%m-%d_%H}'
            path=ROOT/rel
            assert path.is_file(),path
            fields,chunks,digest=wps(path)
            counts={name:sorted(lev for field,lev in fields if field==name and lev<200000) for name in FIELDS}
            assert all(val==sorted(lev*100 for lev in LEVELS) for val in counts.values()),(rel,counts)
            assert len(fields)==172 and entry['records']==172 and digest==entry['sha256'],rel
            assert all(x[0]!='PSFC' for x in fields)
            step_results[(arm,lead)]=chunks
            manifest.append(f'{digest}  {rel}')
        for lead in range(0,n*6,6):
            assert step_results[('AI',lead)]==step_results[('GFS',lead)],(cycle,lead,'shared_surface_byte_mismatch')
            assert len(step_results[('AI',lead)])==15,(cycle,lead,len(step_results[('AI',lead)]))
            all_pairs+=1
        result['cycles'][cycle]={'times_per_arm':n,'files':2*n,'records_per_file':172,'high_air_levels':LEVELS,'shared_surface_fields':15,'byte_identical_pairs':n,'fill_count_by_field':fill_counts,'fill_d01_diagnostic':fill_d01,'fill_ledger':str((OPS/f'SOIL_FILL_SNOWFIX_{cycle}.json')),'build_report':str(OPS/f'WPS_{cycle}_REPORT.json')}
    assert len(manifest)==60 and all_pairs==30
    result['totals']={'files':len(manifest),'paired_times':all_pairs,'all_shared_surface_binary_equal':True,'filled_cells_by_cycle':fills}
    report=OPS/'READBACK_GC37_V2.json'; sums=ROOT/'SHA256SUMS'
    assert not report.exists() and not sums.exists(),('refuse_overwrite',report,sums)
    with report.open('x') as f:json.dump(result,f,indent=2)
    with sums.open('x') as f:f.write('\n'.join(sorted(manifest))+'\n')
    print(json.dumps({'report':str(report),'sha256sums':str(sums),'totals':result['totals'],'cycles':{k:{a:v[a] for a in ('files','byte_identical_pairs','fill_count_by_field')} for k,v in result['cycles'].items()}},indent=2))
if __name__=='__main__':main()
