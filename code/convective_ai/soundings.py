"""Colab: nearest-grid 3h StormCast/HRRR hybrid profiles versus actual IEM RAOB.
The RAOB cycle (00/12Z) is not the ASOS peak time: no temporal interpolation.
"""
import datetime as dt, json, os, time, traceback, warnings, csv
from pathlib import Path
import numpy as np, torch, xarray as xr
from metpy import calc as mpcalc
from metpy.units import units
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO,HRRR,HRRR_FX
from earth2studio.run import deterministic
from earth2studio.io import ZarrBackend
root=Path('/content')
records=json.loads((root/'convective_raob_raw.json').read_text())
station_meta={r['event_id']:(float(r['raob_lat']),float(r['raob_lon'])) for r in csv.DictReader((root/'convective_events.csv').open())}
if os.getenv('LIMIT_EVENTS'):records=records[:int(os.environ['LIMIT_EVENTS'])]
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
levels=[1,2,3,4,5,6,7,8,9,10,11,13,15,20,25,30]
variables=[f'{v}{l}hl' for v in ('u','v','t','q','Z') for l in levels]+[f'p{l}hl' for l in levels if l<=20]
output=root/'convective_soundings.jsonl'; done={r['event_id'] for s in output.read_text().splitlines() if (r:=json.loads(s)).get('status')=='ok'} if output.exists() else set()

# Compare only real above-terrain hybrid levels; compute observed and model diagnostics with same MetPy definitions.
def diagnostic(p_hpa,t_c,td_c,z_m,u_ms,v_ms):
    p=np.asarray(p_hpa,dtype=float);t=np.asarray(t_c,dtype=float);td=np.asarray(td_c,dtype=float);z=np.asarray(z_m,dtype=float);u=np.asarray(u_ms,dtype=float);v=np.asarray(v_ms,dtype=float)
    ix=np.argsort(-p);p,t,td,z,u,v=[a[ix] for a in (p,t,td,z,u,v)]
    keep=np.isfinite(p+t+td+z+u+v)&(p>100)&(p<1100)&(td<=t)&(z>=-100)
    p,t,td,z,u,v=[a[keep] for a in (p,t,td,z,u,v)]
    distinct=np.r_[True,np.diff(p)<-0.02];p,t,td,z,u,v=[a[distinct] for a in (p,t,td,z,u,v)]
    if len(p)<5:return {'error':'insufficient QC layers','n':len(p)}
    P=p*units.hPa;T=t*units.degC;Td=td*units.degC;H=z*units.meter;U=u*units('m/s');V=v*units('m/s')
    out={'n':len(p),'lowest_hpa':round(float(p[0]),1),'highest_hpa':round(float(p[-1]),1),'lowest_height_m':round(float(z[0]),1)}
    for name,fn in [('mucape',lambda:mpcalc.most_unstable_cape_cin(P,T,Td)[0].to('J/kg').magnitude),('dcape',lambda:mpcalc.downdraft_cape(P,T,Td)[0].to('J/kg').magnitude),('shear06',lambda:np.hypot(*[w.to('m/s').magnitude for w in mpcalc.bulk_shear(P,U,V,height=H,bottom=(z[0]*units.meter),depth=6000*units.meter)]))]:
        try:out[name]=round(float(fn()),2)
        except Exception as ex:out[name+'_error']=repr(ex)
    return out

for r in records:
    eid=r['event_id'];
    if eid in done:continue
    t0=time.monotonic()
    try:
        station=station_meta[eid]
        sy,sx=np.unravel_index(np.argmin((model.lat-station[0])**2+(model.lon%360-station[1]%360)**2),model.lat.shape)
        raobtime=dt.datetime.fromisoformat(r['requested_utc']).replace(tzinfo=None);init=raobtime-dt.timedelta(hours=3)
        zpath=root/f'convective_profile_{eid}.zarr'
        if zpath.exists():raise FileExistsError(str(zpath))
        deterministic([init],3,model,HRRR(),ZarrBackend(str(zpath)),output_coords={'variable':np.array(variables),'hrrr_y':np.array([model.hrrr_y[sy]]),'hrrr_x':np.array([model.hrrr_x[sx]])},verbose=False)
        ds=xr.open_zarr(zpath)
        def ai(var):return float(ds[var].isel(time=0,lead_time=3,hrrr_y=0,hrrr_x=0).values)
        ai_data={v:np.array([ai(f'{v}{l}hl') for l in levels]) for v in ('u','v','t','q','Z')}
        pa=np.array([ai(f'p{l}hl') for l in levels if l<=20])
        print('PROFILE_AI',eid,'p',pa[:4],'Z',ai_data['Z'][:4],flush=True)
        if len(pa)!=len(levels):
            ai_data={k:v[:len(pa)] for k,v in ai_data.items()}
        dp=mpcalc.dewpoint_from_specific_humidity(pa*units.Pa,ai_data['q']*units('kg/kg')).to('degC').magnitude
        ai_stats=diagnostic(pa/100,ai_data['t']-273.15,dp,ai_data['Z'],ai_data['u'],ai_data['v'])
        # HRRR operational forecast at same initialization and sounding time, nearest true HRRR grid cell.
        fy,fx=HRRR.grid();iy,ix=np.unravel_index(np.argmin((fy-station[0])**2+(fx%360-station[1]%360)**2),fy.shape)
        arr=HRRR_FX()([init],[dt.timedelta(hours=3)],variables)
        def hr(var):return float(arr.sel(variable=var).values[0,0,iy,ix])
        hr_data={v:np.array([hr(f'{v}{l}hl') for l in levels]) for v in ('u','v','t','q','Z')}
        hp=np.array([hr(f'p{l}hl') for l in levels if l<=20]);hr_data={k:v[:len(hp)] for k,v in hr_data.items()}
        hd=mpcalc.dewpoint_from_specific_humidity(hp*units.Pa,hr_data['q']*units('kg/kg')).to('degC').magnitude
        hr_stats=diagnostic(hp/100,hr_data['t']-273.15,hd,hr_data['Z'],hr_data['u'],hr_data['v'])
        raw=r['profiles'][0]['profile']; valid=[x for x in raw if all(x.get(y) is not None for y in ('pres','hght','tmpc','dwpc','drct','sknt'))]
        uw=np.array([-x['sknt']*0.514444*np.sin(np.deg2rad(x['drct'])) for x in valid]);vw=np.array([-x['sknt']*0.514444*np.cos(np.deg2rad(x['drct'])) for x in valid])
        obs_stats=diagnostic([x['pres'] for x in valid],[x['tmpc'] for x in valid],[x['dwpc'] for x in valid],[x['hght'] for x in valid],uw,vw)
        result={'status':'ok','event_id':eid,'raob_station':r['station'],'raob_utc':r['requested_utc'],'init_utc':init.isoformat()+'Z','lead_h':3,'raob':obs_stats,'ai':ai_stats,'hrrr':hr_stats,'ai_grid':[float(model.lat[sy,sx]),float(model.lon[sy,sx]%360-360)],'hrrr_grid':[float(fy[iy,ix]),float(fx[iy,ix]%360-360)],'runtime_sec':round(time.monotonic()-t0,1),'source':r['url']}
        with output.open('a') as f:f.write(json.dumps(result)+'\n')
        print('SOUNDING_DONE',eid,result,flush=True)
    except Exception as ex:
        traceback.print_exc();result={'status':'error','event_id':eid,'error':repr(ex),'runtime_sec':round(time.monotonic()-t0,1)}
        with output.open('a') as f:f.write(json.dumps(result)+'\n')
        print('SOUNDING_ERROR',result,flush=True)
        if r is records[0]:raise
print('SOUNDING_BATCH_COMPLETE',len(records),flush=True)
