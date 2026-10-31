from huggingface_hub import hf_hub_download
from pathlib import Path
import json,time,traceback
# Detached worker records success/failure independently of CLI tunnel lifetime.

root=Path('/content/ace_formal');root.mkdir(exist_ok=True)
repo='allenai/ACE2-ERA5';rev='f25123c52d7faa8f3533816a311cf3353ee83daa'
files=['ace2_era5_ckpt.tar','inference_config.yaml','initial_conditions/ic_1979.nc']+[f'forcing_data/forcing_{y}.nc' for y in range(1979,2011)]
manifest=[]
for name in files:
 t=time.monotonic();p=Path(hf_hub_download(repo,name,revision=rev,local_dir=str(root)))
 assert p.stat().st_size>100
 manifest.append({'name':name,'bytes':p.stat().st_size})
 print('STAGED',name,p.stat().st_size,round(time.monotonic()-t,1),flush=True)
(root/'staging_manifest_2010.json').open('x').write(json.dumps({'repo':repo,'revision':rev,'files':manifest},indent=2))
(root/'staging_2010.done').open('x').write(json.dumps({'files':len(manifest),'bytes':sum(a['bytes'] for a in manifest)}))
print('STAGING_DONE',len(manifest),sum(a['bytes'] for a in manifest),flush=True)
