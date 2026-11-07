import requests,time,traceback
u='https://storage.googleapis.com/ai2cm-public-requester-pays/2024-11-13-ai2-climate-emulator-v2-amip/data/era5-1deg-1940-2022.zarr/.zmetadata'
r=requests.get(u,headers={'Range':'bytes=0-4095'},timeout=20)
print('ACE GCS',r.status_code,r.text[:400],flush=True)
import xarray as xr
for url in ['gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr','gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3']:
 try:
  t=time.monotonic();d=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)
  print('OPEN',url,round(time.monotonic()-t,1),d.time.values[0],d.time.values[-1],flush=True)
  for v in ('10m_u_component_of_wind','10m_v_component_of_wind'):
   a=d[v];print('VAR',v,a.shape,a.encoding.get('chunks'),str(a.dtype),flush=True)
 except Exception as e:print('ERROR',url,repr(e),flush=True)
