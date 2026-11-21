"""Stage paired SHiELD emulators, then independently run a bounded rollout on Colab."""
import json, os, subprocess, sys, time
from pathlib import Path
import yaml
from huggingface_hub import hf_hub_download

base=Path('/content/ace_stochastic_followup')
base.mkdir(exist_ok=True)
models={
 'det':('allenai/ACE2-SHiELD','13978196694ef4bb20d6f9ed94a83e697adda328','ace2_shield_ckpt.tar','inference_config.yaml'),
 'sto':('allenai/ACE2S-SHiELD-plus','85ac7b78b13cf166d3b86c23c0894f41c97dbddb','ace2s_shield_plus_ckpt.tar','inference_config_amip.yaml'),
}
steps=int(os.environ.get('STEPS','40'))
for label,(repo,revision,ckpt,cfgname) in models.items():
    root=base/label
    if (root/'exit.json').exists():
        raise RuntimeError(f'Existing result; refusing overwrite {root}')
    if (root/'start.lock').exists():
        raise RuntimeError(f'Existing start marker; refusing duplicate {root}')
    root.mkdir(exist_ok=True)
    (root/'start.lock').open('x').write(f'{repo} {revision} {steps}\n')
    for fn in [ckpt,cfgname]:
        t=time.monotonic()
        p=hf_hub_download(repo,fn,revision=revision,local_dir=str(base/'inputs'/label))
        print('FETCH',label,fn,Path(p).stat().st_size,round(time.monotonic()-t,2),flush=True)
    forcing=base/'inputs'/'forcing'
    forcing.mkdir(parents=True,exist_ok=True)
    years=range(1979,1981)
    for y in years:
        fn=f'forcing_data/AMIP/forcing_{y}.nc'
        p=hf_hub_download(models['sto'][0],fn,revision=models['sto'][1],local_dir=str(base/'inputs'/'shared'))
        link=forcing/f'forcing_{y}.nc'
        if not link.exists(): link.symlink_to(p)
        print('FETCH forcing',y,Path(p).stat().st_size,flush=True)
    p=hf_hub_download(models['sto'][0],'initial_conditions/AMIP/ic.nc',revision=models['sto'][1],local_dir=str(base/'inputs'/'shared'))
    cfg=yaml.safe_load((base/'inputs'/label/cfgname).read_text())
    cfg['experiment_dir']=str(root/'output')
    cfg['checkpoint_path']=str(base/'inputs'/label/ckpt)
    cfg['initial_condition']['path']=p
    cfg['forcing_loader']['dataset']['data_path']=str(forcing)
    cfg['forcing_loader']['num_data_workers']=0
    cfg['n_forward_steps']=steps
    cfg['forward_steps_in_memory']=min(50,steps)
    cfg['data_writer']['names']=['UGRD10m','VGRD10m']
    cfg['logging']['log_to_wandb']=False
    (root/'config.yaml').write_text(yaml.safe_dump(cfg))
    print('START',label,steps,time.time(),flush=True)
    t=time.monotonic()
    with (root/'run.log').open('x') as log:
        r=subprocess.run([sys.executable,'-m','fme.ace.inference',str(root/'config.yaml')],stdout=log,stderr=subprocess.STDOUT)
    result={'returncode':r.returncode,'wall_s':time.monotonic()-t,'label':label,'steps':steps,'repo':repo,'revision':revision}
    (root/'exit.json').write_text(json.dumps(result,indent=2))
    print('END',result,flush=True)
    if r.returncode:
        print((root/'run.log').read_text()[-7000:],flush=True)
        raise SystemExit(r.returncode)
print('PAIRED_DONE',flush=True)
