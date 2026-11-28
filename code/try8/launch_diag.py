#!/usr/bin/env python3
"""Colab entry point: exclusive remote root, verified sources, native GPU fixture."""
import hashlib, json, os, pathlib, subprocess, tarfile, time
base=pathlib.Path('/content'); root=base/'try8_diag'; root.mkdir(exist_ok=False)
archive=base/'try8.tar.gz'; manifest=json.loads((base/'try8_manifest.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
with tarfile.open(archive) as tar:
    for m in tar.getmembers():
        p=pathlib.PurePosixPath(m.name)
        assert (p.parts[0]=='FluidX3D_gate0' and '..' not in p.parts and (m.isdir() or m.isfile())), m.name
    tar.extractall(root,filter='data')
src=root/'FluidX3D_gate0'
for name, digest in manifest['sources'].items():
    assert hashlib.sha256((src/'src'/name).read_bytes()).hexdigest()==digest, name
print('SOURCE_VERIFIED',len(manifest['sources']),flush=True)
def run(args, name, env=None):
    with (root/name).open('x') as log:
        proc=subprocess.Popen(args,cwd=src,stdout=log,stderr=subprocess.STDOUT,env=env)
        while proc.poll() is None:
            print('HEARTBEAT',name,time.strftime('%H:%M:%S'),flush=True)
            time.sleep(15)
        print('EXIT',name,proc.returncode,flush=True)
        if proc.returncode: raise RuntimeError(f'{name}: {proc.returncode}')
run(['make','Linux','-j8'],'build.log')
env=dict(os.environ);env['LD_LIBRARY_PATH']=str(src/'src/OpenCL/lib')+':'+env.get('LD_LIBRARY_PATH','')
run([str(src/'bin/FluidX3D')],'wall.log',env)
print('WALL_COMPLETE',flush=True)
