#!/usr/bin/env python3
"""Frozen-card v2 verdict primitives. Offline only; no implicit retrieval or sample run.

Input adapter contract: RAP native cell edges (latitude and longitude degrees), a
2-D/3-D array of each meteorological primitive and common 0.25-degree target
edges. Regrid *primitives* before calling envcheck_gc37x_v1d.profile.
IGRA format: https://ncei.noaa.gov/pub/data/igra/data/igra2-data-format.txt
"""
import datetime as dt
import math
from collections import Counter
import numpy as np

PARAMETERS=('MLCAPE','MUCAPE','SHEAR06','SRH01','SRH03')
NEAR_ZERO={'MLCAPE':100.,'MUCAPE':100.,'SHEAR06':5.,'SRH01':25.,'SRH03':25.}
CENSORS=('删失（缺文件）','删失（文件不符）','删失（与初值相同）',
         '删失（坏场）','删失（坏剖面）','删失（其他越界）','LCL 超顶记 0')

def _integer(line, start, end):
    value=line[start-1:end].strip()
    return int(value) if value else -9999

def read_igra(text):
    """Parse official IGRA2 data-por fixed width, no synthetic permissive tokens."""
    lines=iter(text.splitlines()); output=[]
    for line in lines:
        if not line.startswith('#') or len(line)<71: raise ValueError('IGRA header')
        count=_integer(line,33,36)
        if count<0: raise ValueError('IGRA NUMLEV')
        stamp=dt.datetime(_integer(line,14,17),_integer(line,19,20),
                          _integer(line,22,23),_integer(line,25,26),tzinfo=dt.timezone.utc)
        header={'station':line[1:12].strip(),'valid_time':stamp,
                'lat':_integer(line,56,62)/10000.,'lon':_integer(line,64,71)/10000.}
        levels=[]
        for _ in range(count):
            try: row=next(lines)
            except StopIteration as exc: raise ValueError('truncated IGRA sounding') from exc
            if len(row)<51 or row.startswith('#'): raise ValueError('IGRA level')
            def value(a,b,scale=1.):
                v=_integer(row,a,b)
                return None if v in (-9999,-8888) else v/scale
            direction=value(41,45); speed=value(47,51,10.)
            rad=math.radians(direction) if direction is not None else None
            rh=value(29,33,10.); depression=value(35,39,10.)
            levels.append({'surface':row[1:2]=='1','p':value(10,15,100.),
                           'z':value(17,21),'t':value(23,27,10.),
                           'rh':rh,'dpdp':depression,'u':None if rad is None or speed is None else -speed*math.sin(rad),
                           'v':None if rad is None or speed is None else -speed*math.cos(rad)})
        output.append({**header,'levels':levels})
    return output

def qualify_sounding(sounding):
    """No missing vertical support from observed ground through observed 300 hPa."""
    rows=sounding['levels']; ground=next((r for r in rows if r['surface'] and r['p'] is not None),None)
    if ground is None: return False,'no observed surface'
    usable=[r for r in rows if r['p'] is not None and 300<=r['p']<=ground['p']]
    if not usable or min(r['p'] for r in usable)>300: return False,'does not reach 300 hPa'
    non_surface=[r for r in usable if r is not ground]
    if not non_surface or ground['p']-max(r['p'] for r in non_surface)>50:
        return False,'lowest reported level >50 hPa above surface'
    if any(r['p'] is None or r['z'] is None or r['t'] is None or
           (r['rh'] is None and r['dpdp'] is None) or r['u'] is None or r['v'] is None
           for r in usable): return False,'missing T/humidity/wind/height'
    if any(usable[i]['p']<=usable[i+1]['p'] for i in range(len(usable)-1)):
        return False,'pressure order'
    return True,'qualified'

def sounding_profiles(sounding):
    """Raw resolution and 31 pressure levels + observed surface; reject extrapolation."""
    ok,why=qualify_sounding(sounding)
    if not ok: raise ValueError(why)
    import envcheck_gc37x_v1d as model
    from metpy.calc import specific_humidity_from_dewpoint,dewpoint_from_relative_humidity
    from metpy.units import units
    rows=[r for r in sounding['levels'] if r['p'] is not None and r['p']>=100]
    if not rows or min(r['p'] for r in rows)>100: raise ValueError('profile does not reach 100 hPa')
    p=np.array([r['p'] for r in rows]); z=np.array([r['z'] for r in rows]);
    t=np.array([r['t']+273.15 for r in rows]); u=np.array([r['u'] for r in rows]);v=np.array([r['v'] for r in rows])
    td=[]
    for r in rows:
        if r['dpdp'] is not None: td.append(r['t']-r['dpdp'])
        else: td.append(float(dewpoint_from_relative_humidity((r['t']+273.15)*units.K,r['rh']/100.).to('degC').m))
    q=specific_humidity_from_dewpoint(p*units.hPa,np.array(td)*units.degC).m
    ground=next(r for r in rows if r['surface'])
    soil=ground['z']-1; wind=(ground['u'],ground['v'])
    raw=model.profile(p,z,t,q,u,v,soil,surface_wind=wind)
    target=np.array([x for x in model.LEVELS if min(p)<=x<=max(p)],float)
    # Never present unobserved upper 31-level slots as interpolated truth.
    if min(target)>100: raise ValueError('profile lacks CAPE integration top')
    def interp(a): return np.interp(np.log(target),np.log(p)[::-1],a[::-1])
    fields={key:interp(a) for key,a in [('z',z),('t',t),('q',q),('u',u),('v',v)]}
    full={key:[float(np.interp(np.log(lev),np.log(target)[::-1],a[::-1])) if lev in target else None
               for lev in model.LEVELS] for key,a in fields.items()}
    return {'raw':raw,'31_levels_plus_surface':model.profile(target,*(fields[k] for k in ('z','t','q','u','v')),soil,surface_wind=wind),
            'grid_levels_hpa':list(model.LEVELS),'interpolated_fields':full,
            'unsupported_levels_hpa':[lev for lev in model.LEVELS if lev not in target],
            'surface_observed':ground}

def _overlap(a,b,c,d): return max(0.,min(b,d)-max(a,c))

def conservative_average(values,lat_edges,lon_edges,target_lat_edges,target_lon_edges):
    """Spherical cell-overlap mean; NaN outside complete native coverage."""
    a=np.asarray(values,float); y=np.asarray(lat_edges,float);x=np.asarray(lon_edges,float)
    Y=np.asarray(target_lat_edges,float);X=np.asarray(target_lon_edges,float)
    if a.shape[-2:]!=(len(y)-1,len(x)-1) or any(np.diff(v)<=0 for v in (x,y,X,Y)):
        raise ValueError('grid shape/order')
    area_y=np.sin(np.deg2rad(y));area_Y=np.sin(np.deg2rad(Y))
    wy=np.array([[_overlap(area_Y[i],area_Y[i+1],area_y[j],area_y[j+1]) for j in range(len(y)-1)] for i in range(len(Y)-1)])
    wx=np.array([[_overlap(X[i],X[i+1],x[j],x[j+1]) for j in range(len(x)-1)] for i in range(len(X)-1)])
    weights=np.einsum('ij,kl->ikjl',wy,wx)
    full=np.outer(np.diff(area_Y),np.diff(X))
    out=np.einsum('...jl,ikjl->...ik',a,weights)/full
    coverage=weights.sum(axis=(2,3))
    out[...,~np.isclose(coverage,full,rtol=1e-9,atol=1e-12)]=np.nan
    return out

def validation_time(anchor):
    if anchor.tzinfo is None: raise ValueError('anchor must be UTC-aware')
    a=anchor.astimezone(dt.timezone.utc)
    return a.replace(hour=12 if a.hour>=12 else 0,minute=0,second=0,microsecond=0)

def lead_or_censor(anchor,cycle):
    v=validation_time(anchor)
    lead=(v-cycle.astimezone(dt.timezone.utc)).total_seconds()/3600
    return (lead,'删失（与初值相同）' if lead<6 else None)

def x99_and_distortion(field,reference,parameter):
    if parameter not in NEAR_ZERO: raise ValueError('parameter')
    a=np.asarray(field,float);r=np.asarray(reference,float)
    if a.shape!=r.shape: raise ValueError('same evaluation grid required')
    good=np.isfinite(a)&np.isfinite(r)
    if not np.any(good): return {'status':'删失（坏场）'}
    x=float(np.percentile(a[good],99)); ref=float(np.percentile(r[good],99))
    return {'X99':x,'X99_RAP':ref,'D':None if ref<NEAR_ZERO[parameter] else abs(x-ref)/ref,
            'status':'不判（参照近零）' if ref<NEAR_ZERO[parameter] else '有效'}

def _vote_threshold(n): return math.ceil(2*n/3)

def h1(paired):
    """event -> (D24,D72); 48 h is reporting-only elsewhere."""
    good=[(a,b) for a,b in paired.values() if a is not None and b is not None]
    n=len(good); positives=sum(b>a for a,b in good)
    median=float(np.median([b-a for a,b in good])) if good else None
    verdict='不判'
    if n>=3:
        if positives>=_vote_threshold(n) and median>0: verdict='符合预期'
        elif positives<=n//3: verdict='不符合预期'
    return {'n':n,'positive':positives,'median_delta':median,'verdict':verdict}

def h2(paired,metric='探空点误差'):
    """event -> (AI errors, GFS errors); each side median within event."""
    if metric not in ('探空点误差','极值失真 D'): raise ValueError('metric')
    deltas={}
    for event,(ai,gfs) in paired.items():
        if ai is None or gfs is None: continue
        a=np.asarray(ai,float);g=np.asarray(gfs,float)
        if not a.size or not g.size or not np.all(np.isfinite(a)) or not np.all(np.isfinite(g)): continue
        deltas[event]=float(np.median(a)-np.median(g))
    n=len(deltas); bigger=sum(v>0 for v in deltas.values());smaller=sum(v<0 for v in deltas.values())
    verdict='不判' if n<3 else ('AI 较大' if bigger>=_vote_threshold(n) else 'AI 较小' if smaller>=_vote_threshold(n) else '相当')
    return {'n':n,'AI_minus_GFS':deltas,'AI_bigger':bigger,'AI_smaller':smaller,'verdict':verdict,
            'reference_bias':'参照偏向 GFS 组' if metric=='极值失真 D' else None}

def pearson_report(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);good=np.isfinite(a)&np.isfinite(b)
    if good.sum()<3 or np.std(a[good])==0 or np.std(b[good])==0: return None
    return float(np.corrcoef(a[good],b[good])[0,1])

def report_by_cohort(rows):
    """Rows with cohort=main/secondary, event, group, parameter, lead, D,
    sonde_error, pearson, status. Every absence remains explicit, never imputed."""
    output={}
    for cohort in ('main','secondary'):
        rr=[r for r in rows if r['cohort']==cohort];counts=Counter(r['status'] for r in rr)
        tab={'censor_counts':{key:counts[key] for key in CENSORS},'H1':{},'H2':{},'pearson':{}}
        for p in PARAMETERS:
            for group in ('AI','GFS'):
                matched={}
                for event in {r['event'] for r in rr}:
                    d={r['lead']:r.get('D') for r in rr if r['event']==event and r['group']==group and r['parameter']==p and r['status']=='有效'}
                    matched[event]=(d.get(24),d.get(72))
                tab['H1'][f'{group}:{p}']=h1(matched)
                for lead in (24,48,72):
                    vals=[r['pearson'] for r in rr if r['group']==group and r['parameter']==p and r['lead']==lead and r.get('pearson') is not None]
                    tab['pearson'][f'{group}:{p}:{lead}']={'median':float(np.median(vals)) if vals else None,
                                                             'range':[min(vals),max(vals)] if vals else None,'verdict':'只报告'}
            for lead in (24,48,72):
                paired_err={};paired_d={}
                for event in {r['event'] for r in rr}:
                    by={r['group']:r for r in rr if r['event']==event and r['parameter']==p and r['lead']==lead and r['status']=='有效'}
                    if 'AI' in by and 'GFS' in by:
                        paired_err[event]=(by['AI'].get('sonde_error'),by['GFS'].get('sonde_error'))
                        paired_d[event]=(by['AI'].get('D'),by['GFS'].get('D'))
                tab['H2'][f'{p}:{lead}:sonde']=h2(paired_err)
                tab['H2'][f'{p}:{lead}:D']=h2(paired_d,'极值失真 D')
        output[cohort]=tab
    return output
