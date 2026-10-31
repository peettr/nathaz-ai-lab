"""Fetch public AERO-ODE archives on CRC only; no credentials."""
import io
import os
import sys
import urllib.request
import zipfile

ROOT = '/groups/kareem/[用户]/L26_4_AERO_ODE_20261019'
BASE = 'https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data/resolve/main/'

class HTTPRange(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=90) as r:
            self.length = int(r.headers['Content-Length'])
        self.pos = 0
        self.cache = b''
        self.start = 0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.length - self.pos
        if not n: return b''
        if not (self.start <= self.pos and self.pos+n <= self.start+len(self.cache)):
            end = min(self.length - 1, self.pos + max(n, 1024*1024) - 1)
            req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{end}'})
            with urllib.request.urlopen(req, timeout=120) as response:
                if response.status != 206:
                    raise RuntimeError(f'HTTP Range unsupported: {response.status}')
                self.cache = response.read()
                self.start = self.pos
        result = self.cache[self.pos-self.start:self.pos-self.start+n]
        self.pos += len(result)
        return result

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'list':
        z = zipfile.ZipFile(HTTPRange(BASE+'data.zip'))
        for f in z.infolist():
            print(f.filename, f.file_size, f.compress_size)
    elif mode == 'extract':
        archive = sys.argv[2]
        z = zipfile.ZipFile(HTTPRange(BASE+archive))
        dest = os.path.join(ROOT, 'repo', 'AERO_ODE')
        for f in z.infolist():
            if f.is_dir(): continue
            if archive == 'data.zip':
                path = f.filename.lower()
                # First-stage western reproduction: full April ERA5 and HRRR test,
                # but only select named days if passed after archive name.
                days = set(sys.argv[3:])
                if days and not any(('/04/'+d+'/' in path or '/04/'+d+'.' in path) for d in days) and 'hrrr_stat' not in path:
                    continue
            if os.path.isabs(f.filename) or '..' in f.filename.split('/'):
                raise RuntimeError(f'Unsafe archive path {f.filename}')
            target = os.path.join(dest, f.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target):
                raise FileExistsError(target)
            print('extract', f.filename, f.file_size, flush=True)
            with z.open(f) as src, open(target, 'xb') as out:
                while True:
                    chunk = src.read(1024*1024)
                    if not chunk: break
                    out.write(chunk)
    else: raise ValueError(mode)
