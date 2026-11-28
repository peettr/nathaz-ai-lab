#!/usr/bin/env python3
"""GC37x WPS profile diagnostics; no reference observations are read in v1."""
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import struct
import warnings
from collections import Counter

import numpy as np
import metpy
from metpy.calc import (dewpoint_from_specific_humidity, mixed_layer_cape_cin,
                        most_unstable_cape_cin, bulk_shear, bunkers_storm_motion,
                        storm_relative_helicity, specific_humidity_from_dewpoint,
                        most_unstable_parcel, mixed_parcel, lcl)
from metpy.units import units

METPY_VERSION = '1.6.3'
assert metpy.__version__ == METPY_VERSION, (metpy.__version__, METPY_VERSION)
print('MetPy version:', metpy.__version__, flush=True)


def bounds_warnings(seen):
    return [str(w.message) for w in seen if any(word in str(w.message).lower()
            for word in ('bounds', 'interpolat', 'extrapolat'))]
LEVELS = (1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,
          250,200,150,100,70,50,30,20,10,7,5,3,2,1)
FIELDS = ('GHT','TT','UU','VV','SPECHUMD')
ROOT = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def records(path, points=None):
    """WPS format 5, big-endian Fortran records; points are flat indices."""
    out = {}; grid = None
    with open(path, 'rb') as f:
        def rec():
            b = f.read(4)
            if not b: return None
            if len(b) != 4: raise ValueError('truncated record')
            n, = struct.unpack('>I', b)
            data = f.read(n); end = f.read(4)
            if len(data) != n or end != b: raise ValueError('invalid record framing')
            return data
        while (version := rec()) is not None:
            if version != struct.pack('>I', 5): raise ValueError('not WPS format 5')
            hdr, proj, wind, slab = (rec() for _ in range(4))
            if None in (hdr, proj, wind, slab): raise ValueError('truncated slab')
            field = hdr[60:69].decode('ascii').strip()
            level, nx, ny, iproj = struct.unpack('>fiii', hdr[140:156])
            level = int(round(level))
            if len(hdr) != 156 or len(proj) != 28 or len(wind) != 4 or iproj != 0 or len(slab) != 4*nx*ny:
                raise ValueError('invalid WPS slab')
            coords = (*struct.unpack('>fffff', proj[8:28])[:4], nx, ny)
            if proj[:8] != b'SWCORNER' or (grid is not None and grid != coords): raise ValueError('grid mismatch')
            grid = coords
            key = (field, level)
            if key in out: raise ValueError('duplicate slab ' + str(key))
            if field in FIELDS or (field == 'SOILHGT' and level == 200100):
                array = np.frombuffer(slab, dtype='>f4')
                selected = array if points is None else array[points]
                if not np.isfinite(selected).all(): raise ValueError('nonfinite '+str(key))
                out[key] = selected.astype('f8')
        for field in FIELDS:
            if sorted(k[1] for k in out if k[0] == field and k[1] < 200000) != sorted(100*l for l in LEVELS):
                raise ValueError('incomplete pressure field '+field)
        if ('SOILHGT', 200100) not in out: raise ValueError('missing SOILHGT')
    return out, grid


def field_qc(slabs, idx, return_metrics=False):
    """Whole-grid QC; correlations are measured in the event evaluation box."""
    minimum = {}
    for field in FIELDS:
        for lev in LEVELS:
            arr = slabs[field,100*lev]
            if not np.isfinite(arr).all():
                raise ValueError(f'bad field nonfinite {field} {lev}')
            region = arr[idx]
            if len(region) > 1 and np.ptp(region) == 0 and (field != 'SPECHUMD' or lev >= 300):
                raise ValueError(f'bad field constant {field} {lev}')
            if field == 'SPECHUMD' and lev >= 300 and np.all(region < 1e-5):
                raise ValueError(f'bad field dry SPECHUMD {lev}')
    for field in ('UU','VV'):
        correlations = []
        arrays = [slabs[field,100*lev][idx] for lev in LEVELS]
        for a,b in zip(arrays[:-1], arrays[1:]):
            if np.std(a) == 0 or np.std(b) == 0:
                raise ValueError(f'bad field constant wind {field}')
            correlations.append(float(np.corrcoef(a,b)[0,1]))
        minimum[field] = min(correlations)
        # A reversed interior slab anticorrelates with *both* neighbors.
        for i in range(1,len(arrays)-1):
            if LEVELS[i] >= 300 and correlations[i-1] < 0 and correlations[i] < 0:
                raise ValueError(f'bad field reversed wind {field} {LEVELS[i]} '
                                 f'corr={correlations[i-1]:.6g},{correlations[i]:.6g}')
    return minimum if return_metrics else None


def mask_points(path, lat, lon):
    # Read terrain alone from an authentic WPS stream, then use same flat indices on all slabs.
    slabs, grid = records(path)
    lat0, lon0, dlat, dlon, nx, ny = grid
    jj, ii = np.divmod(np.arange(nx*ny), nx)
    glat = lat0 + jj*dlat
    glon = (lon0 + ii*dlon + 180) % 360 - 180
    dphi = np.deg2rad(glat-lat)
    dlambda = np.deg2rad((glon-lon+180)%360-180)
    a = np.sin(dphi/2)**2 + np.cos(np.deg2rad(lat))*np.cos(np.deg2rad(glat))*np.sin(dlambda/2)**2
    dist = 2*6371.229*np.arcsin(np.sqrt(np.minimum(a, 1)))
    idx = np.flatnonzero((dist <= 500) & (slabs['SOILHGT',200100] < 2000))
    if not len(idx): raise ValueError('empty evaluation area')
    return idx


def surface_pressure(p, z, soil):
    # Exact log-pressure interpolation; extrapolation only below bottom level.
    order = np.argsort(z)
    zz = z[order]; lp = np.log(p[order])
    if not np.all(np.diff(zz) > 0): raise ValueError('nonmonotone GHT')
    if soil <= zz[0]: return float(np.exp(lp[0]+(soil-zz[0])*(lp[1]-lp[0])/(zz[1]-zz[0])))
    if soil >= zz[-1]: raise ValueError('terrain above GHT top')
    return float(np.exp(np.interp(soil, zz, lp)))


def profile(p, z, t, q, u, v, soil, events=None):
    # Warnings outside the CAPE call are also invalid; never silently use them.
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always')
        result=_profile_impl(p,z,t,q,u,v,soil,events)
        if bounds_warnings(seen): raise ValueError('MetPy warning: '+str(bounds_warnings(seen)))
        return result


def _profile_impl(p, z, t, q, u, v, soil, events=None):
    """Common single-column diagnostic path for WPS and sounding test fixture."""
    for name, arr in [('p',p),('z',z),('t',t),('q',q),('u',u),('v',v)]:
        if not np.isfinite(arr).all(): raise ValueError('nonfinite '+name)
    if np.any(q < 0) or np.any(q >= .06): raise ValueError('bad specific humidity')
    if np.any((t < 160) | (t > 345)): raise ValueError('bad temperature')
    if not np.all(np.diff(p) < 0): raise ValueError('pressure order')
    ps = surface_pressure(p,z,soil)
    valid = (p < ps) & (z > soil) & (p >= 100)
    if np.count_nonzero(valid) < 3: raise ValueError('insufficient above-ground layers')
    p,z,t,q,u,v = (arr[valid] for arr in (p,z,t,q,u,v))
    if not np.all(np.diff(z) > 0): raise ValueError('nonmonotone above-ground GHT')
    if z[-1]-soil < 6000: raise ValueError('6km outside profile')
    if np.count_nonzero((p >= ps-100)) < 2 or np.count_nonzero(p >= ps-300) < 2:
        raise ValueError('insufficient parcel layers')
    pp=p*units.hectopascal; tt=t*units.kelvin
    dd=dewpoint_from_specific_humidity(pp,tt,np.maximum(q,1e-10)*units.dimensionless)
    zz=(z-soil)*units.meter; uu=u*units('m/s'); vv=v*units('m/s')
    # MetPy internally applies virtual-temperature correction during parcel buoyancy integration.
    ml_depth=(p[0]-(ps-100))*units.hPa
    mu_depth=(p[0]-(ps-300))*units.hPa
    if ml_depth.m <= 0 or mu_depth.m <= 0: raise ValueError('surface layer top below first level')
    def cape_with_warning_gate(kind, depth):
        # Replicate the parcel selection in MetPy 1.6.3 before parcel_profile_with_lcl.
        # An LCL above the actual available sounding top has no CAPE integral.
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always')
            if kind == 'MLCAPE':
                start_p,start_t,start_td=mixed_parcel(pp,tt,dd,depth=depth)
            else:
                _,_,_,i=most_unstable_parcel(pp,tt,dd,depth=depth)
                start_p,start_t,start_td=pp[i],tt[i],dd[i]
            lp=lcl(start_p,start_t,start_td)[0].to('hPa').m
            start_info={'parcel':kind,'p_hpa':float(start_p.to('hPa').m),
                        'T_K':float(start_t.to('K').m),'Td_K':float(start_td.to('K').m),
                        'LCL_hpa':float(lp),'top_hpa':float(p[-1])}
            if not all(np.isfinite(list(start_info.values())[1:])):
                raise ValueError('nonfinite parcel start/LCL')
            if lp < p[-1]:
                if bounds_warnings(seen): raise ValueError('parcel setup warning: '+str(bounds_warnings(seen)))
                if events is not None: events.append({'type':'LCL 超顶记 0',**start_info})
                return 0.
            calc=mixed_layer_cape_cin if kind == 'MLCAPE' else most_unstable_cape_cin
            result=calc(pp,tt,dd,depth=depth)[0].to('J/kg').m
            if bounds_warnings(seen):
                raise ValueError('MetPy warning: '+str(bounds_warnings(seen))+'; '+str(start_info))
            return float(result)
    ml=cape_with_warning_gate('MLCAPE',ml_depth)
    mu=cape_with_warning_gate('MUCAPE',mu_depth)
    # Flat extension: no shear and no SRH contribution from ground to first layer.
    # For a true ground observation, z[0]-soil is 1 m in the known-answer gate.
    wp=np.r_[ps,p]*units.hectopascal
    wz=np.r_[0,z-soil]*units.meter
    wu=np.r_[u[0],u]*units('m/s');wv=np.r_[v[0],v]*units('m/s')
    du,dv=bulk_shear(wp,wu,wv,height=wz,depth=6000*units.meter)
    shear=np.hypot(du.to('m/s').m,dv.to('m/s').m)
    storm,_,_=bunkers_storm_motion(wp,wu,wv,wz)
    srh1=storm_relative_helicity(wz,wu,wv,depth=1000*units.meter,storm_u=storm[0],storm_v=storm[1])[0].to('m^2/s^2').m
    srh3=storm_relative_helicity(wz,wu,wv,depth=3000*units.meter,storm_u=storm[0],storm_v=storm[1])[0].to('m^2/s^2').m
    ans=dict(MLCAPE=float(ml),MUCAPE=float(mu),SHEAR06=float(shear),SRH01=float(srh1),SRH03=float(srh3))
    if not all(np.isfinite(list(ans.values()))): raise ValueError('nonfinite diagnostic')
    return ans


def manifest_hash(path, report):
    d=json.loads(pathlib.Path(report).read_text())
    rel=path.relative_to(pathlib.Path(report).parent.parent)
    rows=d if isinstance(d,list) else d.get('files',d.get('entries',[]))
    if isinstance(rows,dict): rows=list(rows.values())
    hits=[row['sha256'] for row in rows if isinstance(row,dict) and (row.get('file')==str(rel) or row.get('file')==str(path) or str(row.get('file','')).endswith('/'+str(rel)))]
    if len(hits)!=1: raise ValueError('manifest entry missing or duplicate')
    return hits[0]


def assess(path, event, cycle, report, config, force=False, max_points=None):
    counts=Counter(); validtime=dt.datetime.strptime(path.name,'FILE:%Y-%m-%d_%H')
    t0=dt.datetime.strptime(cycle,'%Y%m%d%H')
    actual=(validtime-t0).total_seconds()/3600
    if not force and actual < 6:
        counts['删失（与初值相同）']+=1
        return {'status':'删失（与初值相同）','actual_lead_h':actual,'counts':dict(counts)}
    if not path.is_file():
        counts['删失（缺文件）']+=1
        return {'status':'删失（缺文件）','counts':dict(counts)}
    try:
        expected=manifest_hash(path,report)
    except (ValueError,KeyError,FileNotFoundError) as exc:
        counts['删失（文件不符）']+=1
        return {'status':'删失（文件不符）','detail':str(exc),'counts':dict(counts)}
    actualsha=sha(path)
    if actualsha!=expected:
        counts['删失（文件不符）']+=1
        return {'status':'删失（文件不符）','sha256':actualsha,'expected':expected,'counts':dict(counts)}
    cfg=json.loads(pathlib.Path(config).read_text())['events'][event]
    try:
        idx=mask_points(path,float(cfg['lat']),float(cfg['lon']))
        all_slabs,_=records(path)
        field_qc(all_slabs,idx)
        if max_points: idx=idx[:max_points]
        slabs,_=records(path,idx)
        p=np.array(LEVELS,dtype=float)
        values={f:np.stack([slabs[f,100*lev] for lev in LEVELS]) for f in FIELDS}
        answers=[]
        for j in range(len(idx)):
            try:
                events=[]
                x=profile(p,values['GHT'][:,j],values['TT'][:,j],values['SPECHUMD'][:,j],values['UU'][:,j],values['VV'][:,j],slabs['SOILHGT',200100][j],events)
                answers.append(x)
                counts['LCL 超顶记 0']+=sum(e['type']=='LCL 超顶记 0' for e in events)
            except (ValueError,IndexError,ArithmeticError) as exc:
                counts['删失（坏剖面）']+=1
                counts['其他越界/插值告警删失']+=int('warning' in str(exc).lower())
                if 'first_bad_profile' not in counts: counts['first_bad_profile']=str(exc)
        if not answers:
            return {'status':'删失（坏剖面）','sha256':actualsha,'grid_count':len(idx),'valid_count':0,
                    'detail':str(counts.get('first_bad_profile')),'counts':dict(counts),
                    'warning_counts':{'LCL 超顶记 0':counts['LCL 超顶记 0'],
                                      '其他越界/插值告警删失':counts['其他越界/插值告警删失']}}
        result={'status':'有效','sha256':actualsha,'actual_lead_h':actual,'grid_count':len(idx),'valid_count':len(answers),'counts':dict(counts),
                'warning_counts':{'LCL 超顶记 0':counts['LCL 超顶记 0'],'其他越界/插值告警删失':counts['其他越界/插值告警删失']}}
        result['X99']={key:float(np.percentile([a[key] for a in answers],99)) for key in answers[0]}
        result['first_column']=answers[0]
        return result
    except (ValueError,KeyError,IndexError,struct.error) as exc:
        label='删失（坏场）' if str(exc).startswith('bad field ') or str(exc).startswith('nonfinite ') else '删失（坏文件）'
        counts[label]+=1
        return {'status':label,'sha256':actualsha,'detail':str(exc),'counts':dict(counts)}


def known_answer():
    from metpy.testing import get_test_data
    source=get_test_data('may4_sounding.txt',as_file_obj=False)
    raw=np.genfromtxt(source,skip_header=5)
    raw=raw[np.isfinite(raw[:,[0,1,2,3,5,6,7]]).all(axis=1) & (raw[:,0]>=100)]
    p,z=raw[:,0],raw[:,1]
    t=raw[:,2]+273.15
    q=specific_humidity_from_dewpoint(p*units.hPa,raw[:,3]*units.degC).m
    direction=np.deg2rad(raw[:,6]);speed=raw[:,7]*0.5144444444444445
    u=-speed*np.sin(direction);v=-speed*np.cos(direction)
    soil=z[0]-1.0
    got=profile(p,z,t,q,u,v,soil)
    pp=p*units.hPa;tt=t*units.K;dd=raw[:,3]*units.degC
    zz=(z-soil)*units.m;uu=u*units('m/s');vv=v*units('m/s')
    storm,_,_=bunkers_storm_motion(pp,uu,vv,zz)
    du,dv=bulk_shear(pp,uu,vv,height=zz,depth=6000*units.m)
    ref={'MLCAPE':float(mixed_layer_cape_cin(pp,tt,dd,depth=100*units.hPa)[0].m),
         'MUCAPE':float(most_unstable_cape_cin(pp,tt,dd,depth=300*units.hPa)[0].m),
         'SHEAR06':float(np.hypot(du.m,dv.m)),
         'SRH01':float(storm_relative_helicity(zz,uu,vv,depth=1000*units.m,storm_u=storm[0],storm_v=storm[1])[0].m),
         'SRH03':float(storm_relative_helicity(zz,uu,vv,depth=3000*units.m,storm_u=storm[0],storm_v=storm[1])[0].m)}
    # Diagnostic only: the observed sounding ends near 269 hPa. Populate all
    # 31 levels with edge-held thermodynamics/winds beyond observed support;
    # extrapolate height in log(p). Never treat these upper levels as truth.
    std=np.array(LEVELS,dtype=float)
    def interp(values): return np.interp(np.log(std),np.log(p)[::-1],values[::-1])
    iz=interp(z)
    low=std>p[0]; high=std<p[-1]
    iz[low]=z[0]+(np.log(std[low])-np.log(p[0]))*(z[2]-z[0])/(np.log(p[2])-np.log(p[0]))
    iz[high]=z[-1]+(np.log(std[high])-np.log(p[-1]))*(z[-1]-z[-5])/(np.log(p[-1])-np.log(p[-5]))
    interp31=profile(std,iz,interp(t),interp(q),interp(u),interp(v),soil)
    removed=profile(p[1:],z[1:],t[1:],q[1:],u[1:],v[1:],z[0])
    results={k:{'script':got[k],'metpy_direct':ref[k],
                'relative_difference':abs(got[k]-ref[k])/max(abs(ref[k]),1e-12)} for k in got}
    print(json.dumps({'test_data':str(source),'surface_m':soil,'surface_hpa':p[0],
                      'results':results,
                      'removed_ground_layer_diagnostic_only':{k:{'value':removed[k],'relative_difference':abs(removed[k]-ref[k])/max(abs(ref[k]),1e-12)} for k in ref},
                      'interpolated_31_levels_diagnostic_only':{k:{'value':interp31[k],'relative_difference':abs(interp31[k]-ref[k])/max(abs(ref[k]),1e-12)} for k in ref},
                      'pass':all(v['relative_difference']<=.01 for v in results.values())},allow_nan=False))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('file',type=pathlib.Path,nargs='?')
    ap.add_argument('--known-answer',action='store_true')
    ap.add_argument('--event',default='N1')
    ap.add_argument('--cycle',default='2024061418')
    ap.add_argument('--report',type=pathlib.Path)
    ap.add_argument('--config',type=pathlib.Path)
    ap.add_argument('--force-t0-gate-test',action='store_true')
    ap.add_argument('--max-points',type=int)
    args=ap.parse_args()
    if args.known_answer:
        known_answer();return
    if not (args.file and args.report and args.config): ap.error('file, --report, --config required')
    print(json.dumps(assess(args.file,args.event,args.cycle,args.report,args.config,args.force_t0_gate_test,args.max_points),ensure_ascii=False,allow_nan=False))

if __name__=='__main__': main()
