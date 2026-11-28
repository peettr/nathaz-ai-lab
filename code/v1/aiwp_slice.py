"""Bounded range-read pilot in a Colab CPU VM; no raw AIWP download."""
import io,time,requests,h5py,json,collections,re
URL='https://noaa-oar-mlwp-data.s3.amazonaws.com/FOUR_v200_GFS/2024/1009/FOUR_v200_GFS_2024100900_f000_f240_06.nc'
SIZE=7472991383
class BoundedRange(io.RawIOBase):
 def __init__(self):
  self.pos=0;self.n=0;self.calls=0;self.cache=collections.OrderedDict();self.t0=time.monotonic();self.session=requests.Session()
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,offset,whence=0):
  self.pos=(offset if whence==0 else self.pos+offset if whence==1 else SIZE+offset);return self.pos
 def read(self,n=-1):
  if n<0:n=SIZE-self.pos
  chunks=[]
  while n>0 and self.pos<SIZE:
   block=self.pos//262144; off=self.pos%262144
   if block not in self.cache:
    if self.n>=150_000_000 or self.calls>=500 or time.monotonic()-self.t0>=180:raise RuntimeError('BOUNDED_STOP bytes=%s calls=%s elapsed=%.1f'%(self.n,self.calls,time.monotonic()-self.t0))
    a=block*262144;b=min(SIZE-1,a+262143)
    r=self.session.get(URL,headers={'Range':f'bytes={a}-{b}'},timeout=30)
    if r.status_code!=206:raise RuntimeError('Not Range: '+str(r.status_code))
    self.cache[block]=r.content;self.n+=len(r.content);self.calls+=1
    if len(self.cache)>256:self.cache.popitem(last=False)
   else:self.cache.move_to_end(block)
   b=self.cache[block];take=min(n,len(b)-off);chunks.append(b[off:off+take]);self.pos+=take;n-=take
  return b''.join(chunks)
 def readinto(self,b):
  data=self.read(len(b));b[:len(data)]=data;return len(data)
 def metrics(self):return {'bytes':self.n,'requests':self.calls,'elapsed_s':round(time.monotonic()-self.t0,2),'file_size':SIZE,'url':URL}
reader=BoundedRange();record={'url':URL}
try:
 with h5py.File(reader,'r') as h:
  allvars=[]
  def visit(name,obj):
   if isinstance(obj,h5py.Dataset):allvars.append((name,obj.shape,str(obj.dtype)))
  h.visititems(visit)
  record['datasets']=allvars
  print('DATASETS',allvars[:100],flush=True)
  for key,shape,dtype in allvars:
   low=key.lower()
   if any(s in low for s in ['mslp','prmsl','10u','10v','u10','v10','u_850','v_850','850']):
    ds=h[key]
    # first noninitial forecast time, bounded 25x25 spatial slice; pressure-level axis is left at first index.
    if len(shape)>=2:
     slices=tuple(1 if i==0 and dim>1 else slice(max(0,dim//2-12),min(dim,dim//2+13)) if i>=len(shape)-2 else 0 for i,dim in enumerate(shape))
     try:
      x=ds[slices];record.setdefault('slices',[]).append({'name':key,'index':str(slices),'shape':list(x.shape),'min':float(x.min()),'max':float(x.max())})
      print('SLICE',record['slices'][-1],flush=True)
     except Exception as ex:record.setdefault('slice_errors',[]).append({'name':key,'error':str(ex)})
     if len(record.get('slices',[]))>=5:break
except Exception as ex:record['error']=repr(ex);print('ERROR',repr(ex),flush=True)
record['metrics']=reader.metrics()
print('FINAL',json.dumps(record,ensure_ascii=False),flush=True)
with open('/content/aiwp_slice_metrics.json','x') as f:json.dump(record,f,indent=2)
