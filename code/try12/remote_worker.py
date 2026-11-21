#!/usr/bin/env python3
"""On Colab only: verify staged source, build and execute two gate fixtures."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,os,sys,time,traceback
B=Path('/content'); R=B/'try12_work';R.mkdir(exist_ok=False)
try:
    for variant in ('noshear','native'):
        archive=B/f'try12_{variant}.tar.gz'; manifest=json.loads((B/f'{variant}_manifest.json').read_text())
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
        root=R/variant;root.mkdir()
        with tarfile.open(archive) as tf:
            for info in tf.getmembers():
                p=Path(info.name)
                assert p.parts[0]=='FluidX3D_gate0' and '..' not in p.parts and (info.isdir() or info.isfile()),info.name
            tf.extractall(root,filter='data')
        source=root/'FluidX3D_gate0'
        for name,sha in manifest['sources'].items():
            assert hashlib.sha256((source/'src'/name).read_bytes()).hexdigest()==sha,name
        print('VERIFIED',variant,manifest['sources'],flush=True)
        for cmd,label in ((['make','Linux','-j8'],'build'),([str(source/'bin/FluidX3D')],'solver')):
            with (root/f'{label}.log').open('x') as log:
                p=subprocess.Popen(cmd,cwd=source,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'LD_LIBRARY_PATH':str(source/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')})
                while p.poll() is None:
                    print('HEARTBEAT',variant,label,time.strftime('%H:%M:%S'),flush=True);time.sleep(15)
                print('EXIT',variant,label,p.returncode,flush=True)
                if p.returncode:raise RuntimeError(f'{variant} {label} exit {p.returncode}')
        (R/f'{variant}.done').write_text('done\n')
    (B/'try12.done').write_text('done\n')
except BaseException:
    traceback.print_exc()
    (B/'try12.failed').write_text(traceback.format_exc())
    raise
