"""Disposable Colab VM: concurrent ZIP-member HTTP-range extraction with CRC validation."""
import concurrent.futures as cf
import hashlib, json, os, pathlib, subprocess, sys, time, zipfile, zlib
from importlib.util import spec_from_file_location, module_from_spec
P=pathlib.Path('/content/l264surface09'); ROOT=P/'AERO_ODE'; BASE='https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/'
spec=spec_from_file_location('prior','/content/l264stage_base09.py'); prior=module_from_spec(spec);spec.loader.exec_module(prior)
EXPECTED={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
P.mkdir(exist_ok=True)
subprocess.run(['git','clone','--filter=blob:none','https://github.com/ZZzzzZZZV/AERO_ODE.git',str(P/'source')],check=True)
subprocess.run(['git','-C',str(P/'source'),'checkout','99516ae9cf71dfa9ac3eb0c96293540c40c46114'],check=True)
subprocess.run(['cp','-a',str(P/'source'/'AERO_ODE'),str(ROOT)],check=True)
assert hashlib.sha256((ROOT/'AERO_Surface_WD/test_film_00z_RMSE.py').read_bytes()).hexdigest()=='515ab6a4f5f4ccffcbca6f743f002eac974133da2a4371a0cf61e4d02a4f0d84'
items=[]
for archive in ('Checkpoints.zip','NeuralGCM_Weights.zip','data.zip'):
 with zipfile.ZipFile(prior.HTTPRange(BASE+archive)) as z:
  for info in z.infolist():
   if info.is_dir():continue
   path=pathlib.PurePosixPath(info.filename)
   if path.is_absolute() or '..' in path.parts:raise ValueError(path)
   if archive=='data.zip':
    if str(path).startswith('data/era5_test/2024/04/'):
     if path.parts[4] not in {f'{i:02d}' for i in [1,2,3,*range(11,31)]}:continue
    elif str(path).startswith('data/hrrr_test/04/'):
     if path.stem not in {f'{i:02d}' for i in [1,2,3,*range(11,31)]}:continue
    elif not str(path).startswith('data/hrrr_stat/'):continue
   elif archive=='Checkpoints.zip':
    path=pathlib.PurePosixPath('AERO_AIR_WD' if path.parts[1]=='AERO_AIR' else 'AERO_Surface_WD',*path.parts[2:])
   dest=ROOT.joinpath(*path.parts)
   if dest.exists():
    if dest.stat().st_size!=info.file_size:raise RuntimeError('collision '+str(dest))
    continue
   items.append((archive,info.filename,str(path),info.file_size,info.CRC))
print('TASKS',len(items),flush=True)

def fetch(item):
 archive,name,rel,size,wantcrc=item
 dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 tmp=dest.with_name(dest.name+'.part');start=time.monotonic()
 if tmp.exists():raise FileExistsError(tmp)
 h=hashlib.sha256();crc=0;n=0
 try:
  # Each task owns an independent random-access HTTP client and ZIP reader.
  with zipfile.ZipFile(prior.HTTPRange(BASE+archive)) as z, z.open(name) as src, tmp.open('xb') as out:
   while block:=src.read(4*1024*1024):
    out.write(block);h.update(block);crc=zlib.crc32(block,crc);n+=len(block)
  if n!=size or crc!=wantcrc:raise RuntimeError(f'ZIP CRC/size mismatch {rel} {n}/{size} {crc}/{wantcrc}')
  if rel in EXPECTED and h.hexdigest()!=EXPECTED[rel]:raise RuntimeError('audited weight mismatch '+rel)
  os.link(tmp,dest);tmp.unlink() # exclusive destination, never overwrite
  return [rel,n,h.hexdigest(),round(time.monotonic()-start,2)]
 except BaseException:
  tmp.unlink(missing_ok=True);raise

start=time.monotonic();results=[]
with cf.ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(fetch,item):item for item in items}
 for future in cf.as_completed(futures):
  result=future.result();results.append(result)
  with (P/'stage_increment.jsonl').open('a') as out:out.write(json.dumps(result)+'\n')
  era=sum(x[0].startswith('data/era5_test/2024/04/') for x in results)
  hrr=sum(x[0].startswith('data/hrrr_test/04/') for x in results)
  print('DONE',len(results),'ERA5',era,'HRRR',hrr,'SECONDS',round(time.monotonic()-start,1),'LAST',result[0],flush=True)
for rel,sha in EXPECTED.items():
 p=ROOT/rel
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise RuntimeError('weight missing/mismatch '+rel)
era=sum(x[0].startswith('data/era5_test/2024/04/') for x in results)
hrr=sum(x[0].startswith('data/hrrr_test/04/') for x in results)
assert era==23 and hrr>=23,(era,hrr)
(P/'stage_manifest.json').write_text(json.dumps(results));(P/'stage.done').write_text('ok\n')
print('STAGED',era,hrr,'TIME',time.monotonic()-start,flush=True)
