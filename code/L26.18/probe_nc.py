import json,pathlib,requests
r=pathlib.Path('/content/L26_18'); target={'al092022':['2022-09-27 11:33:48','2022-09-27 23:27:35'],'al102023':['2023-08-28 23:41:42','2023-08-29 11:33:20','2023-08-29 23:50:46','2023-08-30 11:40:01'],'al092024':['2024-09-25 11:42:40','2024-09-25 23:58:14','2024-09-26 11:49:40','2024-09-26 23:35:27','2024-09-26 23:35:36','2024-09-26 23:37:44']}
rows=[]
for sid,ts in target.items():
 data=json.loads((r/f'meta_{sid}.json').read_text())
 for t in ts:
  match=[x for x in data if x['acquisition_start_time']==t];assert len(match)==1,(sid,t,len(match));rows+=match
for x in rows: print('ROW',x['acquisition_start_time'],x['mission_short'],'eye',x['eye_center'],'qual',x['analysis_center_quality_flag'],'rmax',x['analysis_rmax'],'fix',x['center_fix_url'][-70:],'storm',x['storm_center_fix_url'][-70:],flush=True)
(r/'target_meta.json').write_text(json.dumps(rows,indent=2))
import xarray as xr
for k in [0,6]:
 x=rows[k]; p=r/f'probe_{k}.nc';resp=requests.get(x['data_url'],timeout=90); print('FETCH',k,resp.status_code,len(resp.content),resp.text[:80] if len(resp.content)<300 else '',flush=True);resp.raise_for_status();p.write_bytes(resp.content)
 ds=xr.open_dataset(p); print('NC',k,'DIMS',dict(ds.sizes),'GLOBAL',dict(ds.attrs),'VARIABLES',[(v,dict(ds[v].attrs),str(ds[v].dtype),ds[v].shape) for v in ds.variables],flush=True);ds.close()
