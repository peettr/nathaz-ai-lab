import os,time,subprocess,sys
from pathlib import Path
from huggingface_hub import hf_hub_download
p=Path('/content/ace2');p.mkdir(exist_ok=True)
for name in ['ace2_era5_ckpt.tar','forcing_data/forcing_2001.nc','initial_conditions/ic_2001.nc','inference_config.yaml']:
 t=time.monotonic();f=hf_hub_download('allenai/ACE2-ERA5',name,local_dir=str(p));print('DOWNLOADED',name,os.path.getsize(f),round(time.monotonic()-t,1),flush=True)
print('READY',flush=True)
