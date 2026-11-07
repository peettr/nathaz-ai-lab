import sys, os, time, yaml, subprocess, json
from pathlib import Path
mode=os.environ.get('ACE_MODE','smoke')
base=Path('/content/ace2'); out=Path('/content/ace2_runs')/mode
if out.exists(): raise RuntimeError(f'No overwrite: {out}')
out.mkdir(parents=True)
year=int(os.environ.get('ACE_YEAR','2001'))
steps=int(os.environ.get('ACE_STEPS','40'))
config=yaml.safe_load((base/'inference_config.yaml').read_text())
config['experiment_dir']=str(out)
config['checkpoint_path']=str(base/'ace2_era5_ckpt.tar')
config['initial_condition']['path']=str(base/f'initial_conditions/ic_{year}.nc')
config['initial_condition']['start_indices']['times']=[f'{year}-01-01T00:00:00']
config['forcing_loader']['dataset']['data_path']=str(base/'forcing_data')
config['forcing_loader']['num_data_workers']=0
config['n_forward_steps']=steps
config['forward_steps_in_memory']=min(50,steps)
config['data_writer']['names']=['UGRD10m','VGRD10m']
config['logging']['log_to_wandb']=False
cfg=out/'config.yaml'; cfg.write_text(yaml.safe_dump(config))
print('START',mode,year,steps,time.time(),flush=True)
t=time.monotonic()
with (out/'run.log').open('w') as log:
 p=subprocess.run([sys.executable,'-m','fme.ace.inference',str(cfg)],stdout=log,stderr=subprocess.STDOUT)
wall=time.monotonic()-t
print('END',p.returncode,wall,flush=True)
(out/'exit.json').write_text(json.dumps({'returncode':p.returncode,'wall_s':wall,'year':year,'steps':steps}))
if p.returncode: print((out/'run.log').read_text()[-6000:]);raise SystemExit(p.returncode)
print('FILES',[(str(f),f.stat().st_size) for f in out.rglob('*.nc')],flush=True)
