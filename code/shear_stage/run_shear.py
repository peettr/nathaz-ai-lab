#!/usr/bin/env python3
"""Colab-only isolated shear fixture; exclusive output paths."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,os,time,traceback
B=Path('/content'); R=B/'try13_shear_work'; R.mkdir(exist_ok=False)
try:
    archive=B/'try13_shear.tar.gz'; manifest=json.loads((B/'shear_manifest.json').read_text())
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
    with tarfile.open(archive) as tf:
        for info in tf.getmembers():
            p=Path(info.name)
            assert p.parts[0]=='FluidX3D_gate0' and '..' not in p.parts and (info.isdir() or info.isfile()),info.name
        tf.extractall(R,filter='data')
    source=R/'FluidX3D_gate0'
    for name,sha in manifest['sources'].items():
        assert hashlib.sha256((source/'src'/name).read_bytes()).hexdigest()==sha,name
    print('SHEAR_VERIFIED',manifest['sources'],flush=True)
    for cmd,label in ((['make','Linux','-j8'],'build'),([str(source/'bin/FluidX3D')],'solver')):
        with (R/f'{label}.log').open('x') as log:
            p=subprocess.Popen(cmd,cwd=source,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'LD_LIBRARY_PATH':str(source/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')})
            while p.poll() is None:
                print('HEARTBEAT',label,time.strftime('%H:%M:%S'),flush=True);time.sleep(15)
            print('EXIT',label,p.returncode,flush=True)
            if p.returncode:raise RuntimeError(f'{label} exit {p.returncode}')
    (B/'try13_shear.done').write_text('done\n')
except BaseException:
    traceback.print_exc()
    (B/'try13_shear.failed').write_text(traceback.format_exc())
    raise
