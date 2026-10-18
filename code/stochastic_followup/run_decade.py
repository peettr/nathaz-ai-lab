"""Run ten historical AMIP years for the deterministic and stochastic SHiELD emulators."""
import json, subprocess, sys, time
from pathlib import Path
import yaml
from huggingface_hub import hf_hub_download
base=Path('/content/ace_stochastic_followup')
repo='allenai/ACE2S-SHiELD-plus'
rev='85ac7b78b13cf166d3b86c23c0894f41c97dbddb'
forcing=base/'inputs'/'forcing'
for year in range(1981,1990):
    name=f'forcing_data/AMIP/forcing_{year}.nc'
    p=hf_hub_download(repo,name,revision=rev,local_dir=str(base/'inputs'/'shared'))
    link=forcing/f'forcing_{year}.nc'
    if not link.exists():link.symlink_to(p)
    print('FETCH',year,Path(p).stat().st_size,flush=True)
for label in ('det','sto'):
    root=base/(label+'_decade')
    root.mkdir(exist_ok=False)
    (root/'start.lock').open('x').write('1979-1988 14611 steps\n')
    cfg=yaml.safe_load((base/label/'config.yaml').read_text())
    cfg['experiment_dir']=str(root/'output')
    cfg['n_forward_steps']=14611  # 1979-01-01 06Z through 1988-12-31 18Z
    cfg['forward_steps_in_memory']=50
    (root/'config.yaml').write_text(yaml.safe_dump(cfg))
    t=time.monotonic()
    print('START',label,time.time(),flush=True)
    with (root/'run.log').open('x') as log:
        r=subprocess.run([sys.executable,'-m','fme.ace.inference',str(root/'config.yaml')],stdout=log,stderr=subprocess.STDOUT)
    state={'returncode':r.returncode,'wall_s':time.monotonic()-t,'steps':14611,'label':label}
    (root/'exit.json').write_text(json.dumps(state,indent=2))
    print('END',state,flush=True)
    if r.returncode:
        print((root/'run.log').read_text()[-6000:],flush=True)
        raise SystemExit(r.returncode)
print('DECADE_PAIRED_DONE',flush=True)
