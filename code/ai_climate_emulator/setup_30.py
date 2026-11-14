import time,os,json
from pathlib import Path
from huggingface_hub import hf_hub_download
p=Path('/content/ace2'); manifest={}
for year in range(1979,2010):
 name=f'forcing_data/forcing_{year}.nc';f=p/name
 if not f.exists():
  t=time.monotonic();hf_hub_download('allenai/ACE2-ERA5',name,local_dir=str(p));print('FETCH',year,round(time.monotonic()-t,1),f.stat().st_size,flush=True)
 else: print('PRESENT',year,f.stat().st_size,flush=True)
 manifest[year]=f.stat().st_size
if not (p/'initial_conditions/ic_1979.nc').exists():hf_hub_download('allenai/ACE2-ERA5','initial_conditions/ic_1979.nc',local_dir=str(p))
(p/'forcing_manifest.json').write_text(json.dumps(manifest,indent=2))
print('READY30',sum(manifest.values()),flush=True)
