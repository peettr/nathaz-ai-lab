from huggingface_hub import hf_hub_download
import xarray as xr,zipfile, pathlib
for repo,rev,file in [('nvidia/stormcast-v1-era5-hrrr','6c89a0877a0d6b231033d3b0d8b9828a6f833ed8','metadata.zarr.zip'),('nvidia/stormcast-conus','bc8dd783f96fe0fa75fcff5bb67f66b549a5299f','metadata.nc')]:
 p=hf_hub_download(repo,file,revision=rev)
 print(repo,file,p,pathlib.Path(p).stat().st_size,flush=True)
 if file.endswith('.nc'):
  ds=xr.open_dataset(p); print(ds,flush=True)
 else:
  with zipfile.ZipFile(p) as z:
   print('ZIP NAMES',z.namelist()[:80],flush=True); z.extractall('/content/v1_meta')
  for q in pathlib.Path('/content/v1_meta').iterdir():
   print('CHILD',q,flush=True)
   if q.is_dir():
    try: print(xr.open_zarr(q),flush=True)
    except Exception as e:print('ZERR',repr(e),flush=True)
