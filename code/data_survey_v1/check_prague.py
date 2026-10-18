"""Read TURDATA ZIP central directory and selected members by HTTP ranges."""
import io, zipfile, requests, collections, re, sys, json
URL='https://zenodo.org/api/records/10655033/files/LIDAR_wind_profile_TURDATA.zip/content'
class Remote(io.RawIOBase):
    def __init__(self,url):
        self.url=url; self.s=requests.Session(); self.n=1963148669; self.pos=0; self.cache=collections.OrderedDict();self.bytes=0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self,p,whence=0):
        self.pos=[p,self.pos+p,self.n+p][whence];return self.pos
    def read(self,n=-1):
        if n<0:n=self.n-self.pos
        n=min(n,self.n-self.pos); out=bytearray()
        while n:
            block=self.pos//(1024*1024);off=self.pos%(1024*1024)
            if block not in self.cache:
                start=block*1024*1024;end=min(self.n-1,start+1024*1024-1)
                r=self.s.get(self.url,headers={'Range':f'bytes={start}-{end}'},timeout=100);r.raise_for_status()
                assert r.status_code==206 and len(r.content)==end-start+1,(r.status_code,len(r.content))
                self.cache[block]=r.content;self.bytes+=len(r.content)
                if len(self.cache)>12:self.cache.popitem(last=False)
            b=self.cache[block];take=min(n,len(b)-off);out.extend(b[off:off+take]);self.pos+=take;n-=take
        return bytes(out)
if __name__=='__main__':
    src=Remote(URL)
    with zipfile.ZipFile(src) as z:
        entries=z.infolist();print('ZIP entries',len(entries),'total uncompressed',sum(x.file_size for x in entries),flush=True)
        print('TOP',collections.Counter(x.filename.split('/')[0] for x in entries),flush=True)
        for x in entries[:35]:print('ENTRY',x.filename,x.compress_size,x.file_size,flush=True)
        names=[x for x in entries if re.search('(?i)leg|karl|hpl|readme',x.filename)]
        print('NAMED',len(names),flush=True)
        for x in names[:25]:print('NAMED_ENTRY',x.filename,x.compress_size,x.file_size,flush=True)
        # sample small non-empty member in each family
        chosen=[]
        for key in ('readme','leg','karl'):
            q=[x for x in entries if key in x.filename.lower() and x.file_size<10_000_000 and not x.is_dir()]
            if q:chosen.append(q[0])
        if not chosen:
            chosen=[x for x in entries if x.file_size<10_000_000 and not x.is_dir()][:2]
        for x in dict.fromkeys(chosen):
            print('SAMPLE',x.filename,x.file_size,flush=True)
            data=z.read(x);print('SAMPLE_HEAD',repr(data[:1500]),flush=True)
        counts=collections.Counter((x.filename[:6], 'processed' if '/Processed_' in x.filename else 'raw' if '/Wind_Profile_' in x.filename else 'other') for x in entries if not x.is_dir())
        print('MONTH_COUNTS',json.dumps({f'{a}-{b}':n for (a,b),n in sorted(counts.items())}),flush=True)
        processed=[x for x in entries if '/Processed_' in x.filename]
        for ix in (0,100,len(processed)//2,len(processed)-1):
            x=processed[ix];data=z.read(x)
            print('PROCESSED_SAMPLE',x.filename,repr(data[:3500]),flush=True)
        print('FETCHED_BYTES',src.bytes,flush=True)
