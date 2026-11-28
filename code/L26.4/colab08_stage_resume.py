"""Resume only missing public ZIP members in an ephemeral VM after HTTP 429."""
import concurrent.futures as cf, hashlib, json, os, pathlib, subprocess, time, zipfile, zlib, urllib.error
from importlib.util import spec_from_file_location,module_from_spec
P=pathlib.Path('/content/l264surface08');R=P/'AERO_ODE';BASE='https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/'
spec=spec_from_file_location('base','/content/l264stage_base08.py');base=module_from_spec(spec);spec.loader.exec_module(base)
assert subprocess.check_output(['git','-C',str(P/'source'),'rev-parse','HEAD'],text=True).strip()=='99516ae9cf71dfa9ac3eb0c96293540c40c46114'
assert hashlib.sha256((R/'AERO_Surface_WD/test_film_00z_RMSE.py').read_bytes()).hexdigest()=='515ab6a4f5f4ccffcbca6f743f002eac974133da2a4371a0cf61e4d02a4f0d84'
expected={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
items=[];existing=[]
for archive in ('Checkpoints.zip','NeuralGCM_Weights.zip','data.zip'):
 with zipfile.ZipFile(base.HTTPRange(BASE+archive)) as z:
  for info in z.infolist():
   if info.is_dir():continue
   path=pathlib.PurePosixPath(info.filename)
   if path.is_absolute() or '..' in path.parts:raise ValueError(path)
   if archive=='data.zip':
    if str(path).startswith('data/era5_test/2024/04/'):
     if path.parts[4] not in {f'{d:02d}' for d in [1,2,3,*range(11,31)]}:continue
    elif str(path).startswith('data/hrrr_test/04/'):
     if path.stem not in {f'{d:02d}' for d in [1,2,3,*range(11,31)]}:continue
    elif not str(path).startswith('data/hrrr_stat/'):continue
   elif archive=='Checkpoints.zip':path=pathlib.PurePosixPath('AERO_AIR_WD' if path.parts[1]=='AERO_AIR' else 'AERO_Surface_WD',*path.parts[2:])
   dest=R.joinpath(*path.parts)
   if dest.exists():
    if dest.stat().st_size!=info.file_size:raise RuntimeError('existing size mismatch '+str(dest))
    if str(path) in expected and hashlib.sha256(dest.read_bytes()).hexdigest()!=expected[str(path)]:raise RuntimeError('weight mismatch')
    existing.append(str(path));continue
   items.append((archive,info.filename,str(path),info.file_size,info.CRC))
print('RESUME',len(items),'missing',len(existing),'existing',flush=True)
def fetch(item):
 archive,name,rel,size,crcwant=item;dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 for attempt in range(3):
  tmp=dst.with_name(dst.name+f'.resume08_{attempt}.part')
  try:
   with zipfile.ZipFile(base.HTTPRange(BASE+archive)) as z,z.open(name) as src,tmp.open('xb') as out:
    n=0;crc=0;h=hashlib.sha256()
    while chunk:=src.read(4*1024*1024):out.write(chunk);n+=len(chunk);crc=zlib.crc32(chunk,crc);h.update(chunk)
   if n!=size or crc!=crcwant:raise RuntimeError('CRC/size '+rel)
   if rel in expected and h.hexdigest()!=expected[rel]:raise RuntimeError('weight sha '+rel)
   os.link(tmp,dst);tmp.unlink();return rel
  except urllib.error.HTTPError as e:
   tmp.unlink(missing_ok=True)
   if e.code!=429 or attempt==2:raise
   time.sleep((attempt+1)*45)
  except BaseException:tmp.unlink(missing_ok=True);raise
start=time.monotonic();done=[]
with cf.ThreadPoolExecutor(max_workers=3) as ex:
 for f in cf.as_completed([ex.submit(fetch,item) for item in items]):
  rel=f.result();done.append(rel)
  with (P/'resume_increment.jsonl').open('a') as o:o.write(json.dumps(rel)+'\n')
  print('DONE',len(done),'/',len(items),'seconds',round(time.monotonic()-start,1),rel,flush=True)
for rel,sha in expected.items():
 if hashlib.sha256((R/rel).read_bytes()).hexdigest()!=sha:raise RuntimeError('weight final '+rel)
allfiles=existing+done
assert sum(x.startswith('data/era5_test/2024/04/') for x in allfiles)==23
assert sum(x.startswith('data/hrrr_test/04/') for x in allfiles)>=23
(P/'stage.done').write_text('ok\n');print('STAGE_COMPLETE',len(allfiles),flush=True)
