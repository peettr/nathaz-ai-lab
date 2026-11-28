"""Colab-only isolated setup: public upstream, audited weights, April 11-30 input range."""
import pathlib, subprocess, hashlib, zipfile, json, traceback, zlib, sys
from importlib.util import spec_from_file_location,module_from_spec
P=pathlib.Path('/content/l264surface06'); ROOT=P/'AERO_ODE'
spec=spec_from_file_location('prior','/content/stage_base_l264.py'); prior=module_from_spec(spec);spec.loader.exec_module(prior)
expected={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
def cmd(*a):print('RUN',a,flush=True);subprocess.run(a,check=True)
def main():
 P.mkdir(exist_ok=True)
 cmd('git','clone','--filter=blob:none','https://github.com/ZZzzzZZZV/AERO_ODE.git',str(P/'source'))
 cmd('git','-C',str(P/'source'),'checkout','99516ae9cf71dfa9ac3eb0c96293540c40c46114')
 cmd('cp','-a',str(P/'source'/'AERO_ODE'),str(ROOT))
 manifest=[]
 for archive in ('Checkpoints.zip','NeuralGCM_Weights.zip','data.zip'):
  z=zipfile.ZipFile(prior.HTTPRange(prior.BASE+archive))
  for info in z.infolist():
   if info.is_dir():continue
   path=pathlib.PurePosixPath(info.filename)
   if path.is_absolute() or '..' in path.parts:raise ValueError(path)
   if archive=='data.zip':
    if str(path).startswith('data/era5_test/2024/04/'):
     if path.parts[4] not in {f'{i:02d}' for i in range(11,31)}:continue
    elif str(path).startswith('data/hrrr_test/04/'):
     if path.stem not in {f'{i:02d}' for i in range(11,31)}:continue
    elif str(path).startswith('data/hrrr_stat/'):pass
    else:continue
   elif archive=='Checkpoints.zip':
    path=pathlib.PurePosixPath('AERO_AIR_WD' if path.parts[1]=='AERO_AIR' else 'AERO_Surface_WD',*path.parts[2:])
   dest=ROOT.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():
    if dest.stat().st_size!=info.file_size:raise RuntimeError(f'existing collision {dest}')
    print('EXISTING_SOURCE_STATIC',path,flush=True)
    continue
   sha=hashlib.sha256();crc=0
   print('EXTRACT',archive,path,info.file_size,flush=True)
   with z.open(info) as src,dest.open('xb') as out:
    for block in iter(lambda:src.read(4*1024*1024),b''):
     out.write(block);sha.update(block);crc=zlib.crc32(block,crc)
   if crc!=info.CRC or dest.stat().st_size!=info.file_size:raise RuntimeError(f'ZIP integrity {path}')
   manifest.append((str(path),info.file_size,sha.hexdigest()))
   (P/'stage_increment.json').write_text(json.dumps(manifest))
 hashes={name:h for name,_,h in manifest}
 for rel,h in expected.items():
  if hashes.get(rel)!=h:raise RuntimeError(f'WEIGHT HASH MISMATCH {rel} {hashes.get(rel)}')
 for rel,h in [('AERO_Surface_WD/test_film_00z_RMSE.py','515ab6a4f5f4ccffcbca6f743f002eac974133da2a4371a0cf61e4d02a4f0d84')]:
  if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=h:raise RuntimeError('SCRIPT HASH MISMATCH')
 era=[x for x,_,_ in manifest if x.startswith('data/era5_test/2024/04/')]
 hrr=[x for x,_,_ in manifest if x.startswith('data/hrrr_test/04/')]
 print('STAGED',len(era),len(hrr),'WEIGHTS_VERIFIED 3/3',flush=True)
 assert len(era)==20 and len(hrr)>=20
 (P/'stage_manifest.json').write_text(json.dumps(manifest,indent=2));(P/'stage.done').write_text('ok\n')
try:main()
except BaseException:
 (P/'stage.failed').write_text(traceback.format_exc());traceback.print_exc();raise
