"""Compare same valid-time NOAA HRRR f00 with author's HF HRRR test truth on west grid."""
import pathlib,urllib.request,json,h5py,numpy as np
from eccodes import codes_new_from_message,codes_get,codes_get_array,codes_release
P=pathlib.Path('/content/l264diag04');T=P/'texas'; meta=json.loads((T/'window.json').read_text());y,x=meta['west_offset'];h,w=meta['shape']
url='https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20240401/conus/hrrr.t01z.wrfsfcf00.grib2'
rows=[s.split(':') for s in urllib.request.urlopen(url+'.idx',timeout=60).read().decode().splitlines()]
fields={'T2m':('TMP:2 m above ground',38),'U10':('UGRD:10 m above ground',36),'V10':('VGRD:10 m above ground',37)}
report={'source':'NOAA HRRR f00 2024-04-01 01Z vs AERO-ODE HF data/hrrr_test/04/01.h5 hour 1; same grid','fields':{}}
with h5py.File(P/'AERO_ODE/data/hrrr_test/04/01.h5') as f:
 key='data' if 'data' in f else 'fields'; ds=f[key];report['hf_shape']=list(ds.shape)
 for name,(pat,c) in fields.items():
  i=next(i for i,row in enumerate(rows) if ':'.join(row[3:5])==pat)
  start=int(rows[i][1]);end=int(rows[i+1][1])-1
  with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'}),timeout=90) as r:
   assert r.status==206;raw=r.read()
  g=codes_new_from_message(raw);ny,nx=int(codes_get(g,'Nj')),int(codes_get(g,'Ni'))
  noaa=np.asarray(codes_get_array(g,'values'),dtype=np.float32).reshape(ny,nx)[y:y+h,x:x+w];codes_release(g)
  hf=np.asarray(ds[1,c]);assert hf.shape==noaa.shape,(hf.shape,noaa.shape)
  z=hf-noaa
  report['fields'][name]={'max_abs':float(abs(z).max()),'mean_bias':float(z.mean()),'rmse':float(np.sqrt(np.mean(z*z))),'pearson_r':float(np.corrcoef(hf.ravel(),noaa.ravel())[0,1]),'source_range':[float(noaa.min()),float(noaa.max())],'hf_range':[float(hf.min()),float(hf.max())]}
(T/'noaa_hf_truth_diag.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
