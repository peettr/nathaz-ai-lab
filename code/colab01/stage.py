"""Run ONLY inside disposable Colab VM: stage pinned AERO-ODE public inputs."""
import hashlib, os, pathlib, subprocess, sys, time, zipfile, io, urllib.request
BASE='https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/'
ROOT=pathlib.Path('/content/l264h100/AERO_ODE')
WORK=ROOT.parent
class HTTPRange(io.RawIOBase):
    def __init__(self,url):
        self.url=url
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=90) as r:self.length=int(r.headers['Content-Length'])
        self.pos=0;self.start=0;self.cache=b''
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,n,whence=0):
        self.pos=n if whence==0 else self.pos+n if whence==1 else self.length+n
        return self.pos
    def read(self,n=-1):
        if n<0:n=self.length-self.pos
        if not n:return b''
        if not(self.start<=self.pos and self.pos+n<=self.start+len(self.cache)):
            end=min(self.length-1,self.pos+max(n,1048576)-1)
            with urllib.request.urlopen(urllib.request.Request(self.url,headers={'Range':f'bytes={self.pos}-{end}'}),timeout=120) as r:
                if r.status!=206:raise RuntimeError(f'Range not supported: {r.status}')
                self.cache=r.read();self.start=self.pos
        data=self.cache[self.pos-self.start:self.pos-self.start+n];self.pos+=len(data);return data

def cmd(*args):
    print('RUN',args,flush=True)
    subprocess.run(args,check=True)

def extract(archive):
    z=zipfile.ZipFile(HTTPRange(BASE+archive))
    accepted=[]
    for info in z.infolist():
        path=pathlib.PurePosixPath(info.filename)
        if info.is_dir():continue
        if path.is_absolute() or '..' in path.parts:raise ValueError(path)
        if archive=='data.zip':
            if str(path).startswith('data/era5_test/2024/04/'):
                if path.parts[4] not in {f'{x:02d}' for x in range(1,14)}:continue
            elif str(path).startswith('data/hrrr_test/04/'):
                if path.stem not in {f'{x:02d}' for x in range(1,14)}:continue
            elif str(path).startswith('data/hrrr_stat/'):
                pass
            else:continue
        elif archive=='Checkpoints.zip':
            if path.parts[0]!='Checkpoints':raise ValueError(path)
            # Archive uses generic AIR/Surface directory names; README expects AERO_AIR_WD/AERO_Surface_WD.
            path=pathlib.PurePosixPath('AERO_AIR_WD' if path.parts[1]=='AERO_AIR' else 'AERO_Surface_WD',*path.parts[2:])
        dest=ROOT.joinpath(*path.parts)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise FileExistsError(dest)
        print('EXTRACT',archive,str(path),info.file_size,flush=True)
        h=hashlib.sha256()
        with z.open(info) as src,open(dest,'xb') as dst:
            while block:=src.read(4*1024*1024):dst.write(block);h.update(block)
        accepted.append((str(path),info.file_size,h.hexdigest()))
    return accepted

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    cmd('git','clone','--filter=blob:none','https://github.com/ZZzzzZZZV/AERO_ODE.git',str(WORK/'source'))
    cmd('git','-C',str(WORK/'source'),'checkout','99516ae9cf71dfa9ac3eb0c96293540c40c46114')
    cmd('cp','-a',str(WORK/'source'/'AERO_ODE'),str(ROOT))
    import json
    manifest=[]
    for archive in ('Checkpoints.zip','NeuralGCM_Weights.zip','data.zip'):
        manifest+=extract(archive)
        (WORK/'stage_increment.json').write_text(json.dumps(manifest,indent=2))
    expected={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
    hashes={p:h for p,size,h in manifest}
    for p,h in expected.items():
        if hashes.get(p)!=h:raise RuntimeError(f'AUDIT SHA MISMATCH {p}: {hashes.get(p)}')
    print('WEIGHT_HASHES_MATCH 3/3',flush=True)
    (WORK/'stage.done').write_text('ok\n')
if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback;traceback.print_exc();(WORK/'stage.failed').write_text(traceback.format_exc());raise
