"""AIWP forecast against same-level ERA5, diurnally aligned persistence.
Usage: python run.py --limit 1 --models PANG; outputs append-only JSONL.
"""
import argparse,csv,datetime as dt,json,math,time,traceback,pathlib,os,calendar
import numpy as np,h5py,fsspec,zarr,gcsfs,metpy.calc as mp
from metpy.units import units
R=pathlib.Path(__file__).parent; BASE='https://noaa-oar-mlwp-data.s3.amazonaws.com/'
GCS='gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
LEV=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
MAP={'temperature':'t','specific_humidity':'q','u_component_of_wind':'u','v_component_of_wind':'v','geopotential':'z','2m_temperature':'t2','10m_u_component_of_wind':'u10','10m_v_component_of_wind':'v10','geopotential_at_surface':'zsfc'}
def grid(lat,lon):
 i=int(round((90-lat)*4)); j=int(round((lon%360)*4));return slice(i-1,i+2),slice(j-1,j+2)
def era_fields(g,valid,lat,lon,full=False):
 la,lo=grid(lat,lon);ti=int((np.datetime64(valid)-np.datetime64('1900-01-01T00'))/np.timedelta64(1,'h'))
 level=g['level'][:].astype(int);ids=np.argsort(-level) if full else np.array([int(np.flatnonzero(level==x)[0]) for x in LEV]); a={'level':level[ids]}
 for src,k in MAP.items():
  arr=g[src];v=np.asarray(arr[ti,:,la,lo] if arr.ndim==4 else arr[ti,la,lo],dtype=np.float64)
  a[k]=v[ids] if arr.ndim==4 else v
 return a
def aiwp_fields(model,init,lead,lat,lon):
 stem=f'{model}_v100_GFS';key=f'{stem}/{init:%Y}/{init:%m%d}/{stem}_{init:%Y%m%d%H}_f000_f240_06.nc'
 url=BASE+key; f=fsspec.open(url,'rb',block_size=128*1024,cache_type='bytes').open()
 try:
  with h5py.File(f,'r') as h:
   assert h.attrs['initialization_time'].decode()==init.strftime('%Y-%m-%dT%H:%M:%S')
   lev=h['level'][:].astype(int);assert list(lev)==LEV
   actual=np.array(h['time'][:]);target=calendar.timegm((init+dt.timedelta(hours=lead)).timetuple());matches=np.flatnonzero(actual==target)
   if len(matches)!=1:raise ValueError(f'wrong valid time requested {target} vs {actual[:4]}')
   ti=int(matches[0]);la,lo=grid(lat,lon)
   a={'level':lev,'url':url,'forecast_index':ti,'init':init.isoformat()}
   for k in ['t','q' if model!='FOUR' else 'r','u','v','z','t2','u10','v10']:
    a[k]=np.asarray(h[k][ti,:,la,lo] if h[k].ndim==4 else h[k][ti,la,lo],dtype=np.float64)
   return a
 finally:f.close()
def diagnose(a,terrain):
 results={k:[] for k in ['MUCAPE','MLCAPE','DCAPE','shear06','shear01']};invalid=[]
 for i in range(3):
  for j in range(3):
   try:
    p=np.asarray(a['level']); t=a['t'][:,i,j];q=a.get('q');z=a['z'][:,i,j]/9.80665;hs=float(terrain[i,j]/9.80665)
    ok=np.isfinite(t)&np.isfinite(z)&(z>=hs-1)
    p,t,z=p[ok],t[ok],z[ok]
    if len(p)<6:raise ValueError('too few above-ground levels')
    pq=p*units.hPa;T=t*units.kelvin
    if q is not None:td=mp.dewpoint_from_specific_humidity(pq,T,np.clip(q[:,i,j][ok],1e-8,.1)*units.dimensionless)
    else:td=mp.dewpoint_from_relative_humidity(T,np.clip(a['r'][:,i,j][ok],.1,100)/100)
    for k,func in [('MUCAPE',mp.most_unstable_cape_cin),('MLCAPE',mp.mixed_layer_cape_cin)]:
     try:results[k].append(max(0.,float(func(pq,T,td)[0].to('J/kg').m)))
     except Exception as ex:invalid.append(f'{i},{j} {k}: {ex}')
    try:results['DCAPE'].append(max(0.,float(mp.downdraft_cape(pq,T,td)[0].to('J/kg').m)))
    except Exception as ex:invalid.append(f'{i},{j} DCAPE: {ex}')
    heights=np.r_[10,z-hs];u=np.r_[a['u10'][i,j],a['u'][:,i,j][ok]];v=np.r_[a['v10'][i,j],a['v'][:,i,j][ok]]
    if not np.all(np.diff(heights)>0):raise ValueError('non-monotone geopotential heights')
    for k,depth in [('shear01',1000.),('shear06',6000.)]:
     if heights[-1]<depth+10:continue
     # vector wind difference (10 m reference) at interpolated upper AGL height
     results[k].append(float(np.hypot(np.interp(depth+10,heights,u)-u[0],np.interp(depth+10,heights,v)-v[0])))
   except Exception as ex:invalid.append(f'{i},{j} profile: {ex}')
 return {k:(max(v) if v else None) for k,v in results.items()},invalid[:12]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=40);ap.add_argument('--shard',type=int,default=0);ap.add_argument('--shards',type=int,default=1);ap.add_argument('--models',nargs='+',default=['PANG','GRAP','FOUR']);ap.add_argument('--leads',nargs='+',type=int,default=[12,24,48,72,120]);ar=ap.parse_args()
 events=[e for i,e in enumerate(csv.DictReader((R/'events_M.csv').open())) if i<ar.limit and i%ar.shards==ar.shard]
 output=R/f'raw_shard_{ar.shard:02d}.jsonl';done=set()
 for source in [R/'raw_cases.jsonl']+list(R.glob('raw_shard_*.jsonl')):
  if not source.exists():continue
  for line in source.open():
   try:
    row=json.loads(line)
    if row.get('status')=='ok':done.add((row['event_id'],row['model'],row['lead_h']))
   except:pass
 print('START',len(events),'models',ar.models,'leads',ar.leads,'completed',len(done),flush=True)
 g=zarr.open(gcsfs.GCSFileSystem(token='anon').get_mapper(GCS),mode='r')
 refs={}
 for e in events:
  eid=e['event_id'];valid=dt.datetime.fromisoformat(e['verification_utc'].rstrip('Z'));la=float(e['lat']);lo=float(e['lon'])
  if all((eid,m,l) in done for m in ar.models for l in ar.leads):continue
  try:
   ver=era_fields(g,valid,la,lo);terrain=ver['zsfc'];ref,ref_errors=diagnose(ver,terrain)
   ref37,ref37_errors=diagnose(era_fields(g,valid,la,lo,True),terrain)
   refs[eid]=(ref,ref37,terrain)
   print('REFERENCE',eid,valid,ref,'full37',ref37,'errors',ref_errors[:2],flush=True)
  except Exception as ex:
   print('REFERENCE_ERROR',eid,str(ex),traceback.format_exc(),flush=True);continue
  for lead in ar.leads:
   # diurnally aligned persistence; nearest preceding 24h multiple
   lag=24*math.ceil(lead/24)
   try:base,b_errors=diagnose(era_fields(g,valid-dt.timedelta(hours=lag),la,lo),terrain)
   except Exception as ex:print('BASE_ERROR',eid,lead,str(ex),flush=True);continue
   for model in ar.models:
    if (eid,model,lead) in done:continue
    start=time.monotonic();row=dict(event_id=eid,model=model,lead_h=lead,valid=valid.isoformat(),init=(valid-dt.timedelta(hours=lead)).isoformat(),baseline_lag_h=lag,reference=ref,reference_37=ref37,baseline=base,station=e['station'])
    try:
     fc=aiwp_fields(model,valid-dt.timedelta(hours=lead),lead,la,lo)
     forecast,errors=diagnose(fc,terrain);row.update(forecast=forecast,source_url=fc['url'],forecast_index=fc['forecast_index'],diagnosis_errors=errors,status='ok')
    except Exception as ex:row.update(status='error',error=str(ex))
    row['seconds']=round(time.monotonic()-start,2)
    with output.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
    done.add((eid,model,lead));print('CASE',eid,model,lead,row['status'],row['seconds'],row.get('error',''),flush=True)
 print('END',len(done),flush=True)
if __name__=='__main__':main()
