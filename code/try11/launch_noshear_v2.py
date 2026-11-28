#!/usr/bin/env python3
"""Colab entry; exclusive remote root and native OpenCL fixture."""
import hashlib,json,os,pathlib,subprocess,tarfile,time
base=pathlib.Path('/content');root=base/'try11_noshear_v2';root.mkdir(exist_ok=False)
archive=base/'try11_noshear_v2.tar.gz';m=json.loads((base/'try11_noshear_v2_manifest.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['archive_sha256']
with tarfile.open(archive) as tar:
    for f in tar.getmembers():
        p=pathlib.PurePosixPath(f.name)
        assert p.parts[0]=='FluidX3D_gate0' and '..' not in p.parts and (f.isdir() or f.isfile()),f.name
    tar.extractall(root,filter='data')
src=root/'FluidX3D_gate0'
for name,h in m['sources'].items():assert hashlib.sha256((src/'src'/name).read_bytes()).hexdigest()==h,name
print('SOURCE_VERIFIED',len(m['sources']),flush=True)
def run(argv,name):
    with (root/name).open('x') as out:
        p=subprocess.Popen(argv,cwd=src,stdout=out,stderr=subprocess.STDOUT,env={**os.environ,'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')})
        while p.poll() is None:
            print('HEARTBEAT',name,time.strftime('%H:%M:%S'),flush=True);time.sleep(15)
        print('EXIT',name,p.returncode,flush=True)
        if p.returncode:raise RuntimeError(f'{name}: {p.returncode}')
run(['make','Linux','-j8'],'build.log')
run([str(src/'bin/FluidX3D')],'wall.log')
(root/'done').write_text('done\n')
print('WALL_COMPLETE',flush=True)
