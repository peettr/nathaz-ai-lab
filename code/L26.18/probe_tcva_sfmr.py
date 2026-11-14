import json,pathlib,requests,xarray as xr
r=pathlib.Path('/content/L26_18'); rows=json.loads((r/'target_meta.json').read_text())
for k in [1,5,6]:
 x=rows[k];u=x['l2_sar_fix_product_url'];print('TCVA_URL',k,u[-100:],flush=True)
 if not u:continue
 try:
  z=requests.get(u,timeout=90);print('TCVA_FETCH',k,z.status_code,len(z.content),z.text[:100] if len(z.content)<1000 else '',flush=True)
  if z.ok and len(z.content)>5000:
   p=r/f'tcva_probe_{k}.nc';p.write_bytes(z.content);ds=xr.open_dataset(p,decode_times=False);print('TCVA',k,'dims',dict(ds.sizes),'attrs',str(ds.attrs)[:5000],'flags',[(v,str(ds[v].values)[:200],str(ds[v].attrs)[:500]) for v in ds.variables if any(s in v.lower() for s in ['center','flag','rmax','track'])][:35],flush=True);ds.close()
 except Exception as e:print('ERR',repr(e),flush=True)
u='https://erddap.aoml.noaa.gov/hdb/erddap/info/sfmr_2018_2022/index.json';z=requests.get(u,timeout=45);print('ERDDAP',z.status_code,len(z.content),z.text[:140],flush=True)
if z.ok:(r/'sfmr_info.json').write_bytes(z.content)
