"""Disposable Colab stage of official commit and pinned environment; outputs stay on VM."""
import pathlib,subprocess,urllib.request,zipfile,io,hashlib,json,zlib,traceback,time
P=pathlib.Path('/content/l264texas01'); R=P/'AERO_ODE'; P.mkdir(exist_ok=True)
BASE='https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/'
class HTTPRange(io.RawIOBase):
 def __init__(self,url):
  self.url=url
  with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60) as r:self.length=int(r.headers['Content-Length'])
  self.pos=0;self.start=0;self.cache=b''
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,n,w=0):self.pos=n if w==0 else self.pos+n if w==1 else self.length+n;return self.pos
 def read(self,n=-1):
  if n<0:n=self.length-self.pos
  if not n:return b''
  if not(self.start<=self.pos and self.pos+n<=self.start+len(self.cache)):
   end=min(self.length-1,self.pos+max(n,1048576)-1)
   with urllib.request.urlopen(urllib.request.Request(self.url,headers={'Range':f'bytes={self.pos}-{end}'}),timeout=120) as r:
    if r.status!=206:raise RuntimeError(f'HTTP range failed {r.status}')
    self.cache=r.read();self.start=self.pos
  data=self.cache[self.pos-self.start:self.pos-self.start+n];self.pos+=len(data);return data

def run(*a):print('RUN',a,flush=True);subprocess.run(a,check=True)
def extract(archive):
 z=zipfile.ZipFile(HTTPRange(BASE+archive)); out=[]
 for inf in z.infolist():
  rel=pathlib.PurePosixPath(inf.filename)
  if inf.is_dir():continue
  if rel.is_absolute() or '..' in rel.parts:raise ValueError(rel)
  if archive=='data.zip':
   if str(rel).startswith('data/era5_test/2024/04/'):
    if rel.parts[4] not in {f'{i:02d}' for i in range(1,14)}:continue
   elif str(rel).startswith('data/hrrr_stat/'):pass
   else:continue
  elif archive=='Checkpoints.zip':
   rel=pathlib.PurePosixPath('AERO_AIR_WD' if rel.parts[1]=='AERO_AIR' else 'AERO_Surface_WD',*rel.parts[2:])
  dest=R.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():
   if dest.stat().st_size!=inf.file_size:raise RuntimeError(f'existing size mismatch {rel}')
   crc=0
   with dest.open('rb') as f:
    for b in iter(lambda:f.read(4*1024*1024),b''):crc=zlib.crc32(b,crc)
   if crc!=inf.CRC:raise RuntimeError(f'existing CRC mismatch {rel}')
   print('VERIFIED',str(rel),flush=True)
  else:
   print('EXTRACT',str(rel),inf.file_size,flush=True)
   with z.open(inf) as src,dest.open('xb') as dst:
    for b in iter(lambda:src.read(4*1024*1024),b''):dst.write(b)
  out.append((str(rel),inf.file_size))
  (P/'stage_increment.json').write_text(json.dumps(out))
 return out
try:
 run('git','clone','--filter=blob:none','https://github.com/ZZzzzZZZV/AERO_ODE.git',str(P/'source'))
 run('git','-C',str(P/'source'),'checkout','99516ae9cf71dfa9ac3eb0c96293540c40c46114')
 run('cp','-a',str(P/'source'/'AERO_ODE'),str(R))
 for name in ('Checkpoints.zip','NeuralGCM_Weights.zip','data.zip'):extract(name)
 expected={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
 for rel,h in expected.items():
  obj=R/rel
  if not obj.exists() or hashlib.sha256(obj.read_bytes()).hexdigest()!=h:raise RuntimeError(f'WEIGHT SHA MISMATCH {rel}')
 print('WEIGHT_HASHES_MATCH 3/3',flush=True)
 run('uv','python','install','3.10');run('uv','venv','--python','3.10',str(P/'venv'));py=str(P/'venv/bin/python')
 run('uv','pip','install','--python',py,'torch==2.4.0+cu121','torchvision==0.19.0+cu121','--index-url','https://download.pytorch.org/whl/cu121')
 run('uv','pip','install','--python',py,'jax[cuda12]==0.4.29','jaxlib==0.4.29','numpy==1.26.4','ml-dtypes==0.5.3','xarray==2025.6.1','netCDF4==1.7.2','h5py==3.12.1','matplotlib==3.10.0','scipy==1.15.3','dm-haiku==0.0.14','dinosaur==1.3.4','neuralgcm==1.0.0','optax==0.2.5','tensorflow-probability==0.25.0','zarr==2.18.3','numcodecs==0.13.1','pandas==2.3.1','dask==2025.7.0','gin-config==0.5.0','grain==0.2.13','cartopy==0.25.0','cf-xarray==0.10.6','tensorstore==0.1.76','eccodes==2.44.0')
 run('uv','pip','install','--python',py,'--no-deps','-e',str(R/'physics_core/dinosaur-main/dinosaur-main'),'-e',str(R/'physics_core/neuralgcm-main'))
 run(py,'-c',"import torch,jax,eccodes;print('VERSIONS',torch.__version__,jax.__version__,'GPU',torch.cuda.get_device_name(0),jax.devices('gpu'),flush=True)")
 (P/'stage.done').write_text('ok\n')
except BaseException:
 (P/'stage.failed').write_text(traceback.format_exc());traceback.print_exc();raise
