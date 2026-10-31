"""Optimized independent data-only staging; never overwrites original partial extraction."""
import pathlib,hashlib,io,urllib.request,zipfile,zlib,json,traceback,time
BASE='https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/data.zip'
ROOT=pathlib.Path('/content/l264a100/fast_data');ROOT.mkdir(parents=True,exist_ok=True)
class Reader(io.RawIOBase):
 def __init__(self):
  self.url=BASE
  with urllib.request.urlopen(urllib.request.Request(BASE,method='HEAD'),timeout=90) as resp:self.length=int(resp.headers['Content-Length'])
  self.pos=self.start=0;self.cache=b''
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,n,whence=0):
  self.pos=n if whence==0 else self.pos+n if whence==1 else self.length+n;return self.pos
 def read(self,n=-1):
  if n<0:n=self.length-self.pos
  if not n:return b''
  if not(self.start<=self.pos and self.pos+n<=self.start+len(self.cache)):
   end=min(self.length-1,self.pos+max(n,16*1024*1024)-1)
   for attempt in range(3):
    try:
     with urllib.request.urlopen(urllib.request.Request(self.url,headers={'Range':f'bytes={self.pos}-{end}'}),timeout=180) as resp:
      if resp.status!=206:raise RuntimeError('no range response')
      self.cache=resp.read();self.start=self.pos
      if len(self.cache)!=end-self.start+1:raise RuntimeError('short read')
     break
    except Exception:
     if attempt==2:raise
     time.sleep(3*(attempt+1))
  out=self.cache[self.pos-self.start:self.pos-self.start+n];self.pos+=len(out);return out

def main():
 z=zipfile.ZipFile(Reader());manifest=[]
 for inf in z.infolist():
  name=pathlib.PurePosixPath(inf.filename)
  if inf.is_dir():continue
  if name.is_absolute() or '..' in name.parts:raise RuntimeError('unsafe archive member')
  if str(name).startswith('data/era5_test/2024/04/'):
   if name.parts[4] not in {f'{i:02d}' for i in range(1,14)}:continue
  elif str(name).startswith('data/hrrr_test/04/'):
   if name.stem not in {f'{i:02d}' for i in range(1,14)}:continue
  elif str(name).startswith('data/hrrr_stat/'):pass
  else:continue
  dest=ROOT.joinpath(*name.parts);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():
   crc=0
   with dest.open('rb') as f:
    for b in iter(lambda:f.read(4194304),b''):crc=zlib.crc32(b,crc)
   if dest.stat().st_size!=inf.file_size or crc!=inf.CRC:raise RuntimeError('Existing mismatched result: '+str(dest))
   print('PRESERVE',name,flush=True);continue
  print('EXTRACT_FAST',name,inf.file_size,flush=True)
  h=hashlib.sha256()
  with z.open(inf) as src,dest.open('xb') as f:
   while b:=src.read(4194304):f.write(b);h.update(b)
  manifest.append({'path':str(name),'size':inf.file_size,'sha256':h.hexdigest()})
  (ROOT/'fast_increment.json').write_text(json.dumps(manifest,indent=2))
 print('FAST_STAGE_COMPLETE',len(manifest),flush=True)
 (ROOT/'fast.done').write_text(json.dumps({'files':len(manifest)},indent=2))
if __name__=='__main__':
 try:main()
 except BaseException:
  (ROOT/'fast.failed').write_text(traceback.format_exc());traceback.print_exc();raise
