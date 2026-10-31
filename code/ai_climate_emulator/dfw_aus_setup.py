"""Stage ACE2-ERA5 checkpoint and historical forcing on ephemeral Colab."""
from pathlib import Path
from huggingface_hub import hf_hub_download
import time, json
root=Path('/content/ace2');root.mkdir(exist_ok=True)
names=['ace2_era5_ckpt.tar','inference_config.yaml','initial_conditions/ic_1979.nc']+[f'forcing_data/forcing_{y}.nc' for y in range(1979,2010)]
manifest={}
for name in names:
    t=time.monotonic()
    f=hf_hub_download('allenai/ACE2-ERA5',name,revision='f25123c52d7faa8f3533816a311cf3353ee83daa',local_dir=str(root))
    manifest[name]=Path(f).stat().st_size
    print('FETCH',name,manifest[name],round(time.monotonic()-t,2),flush=True)
(root/'dfw_aus_manifest.json').write_text(json.dumps(manifest,indent=2))
print('STAGING_DONE',sum(manifest.values()),flush=True)
