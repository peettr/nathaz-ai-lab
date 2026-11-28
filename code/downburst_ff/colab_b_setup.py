import gzip, os, tarfile, shutil, sys, subprocess, json, time
from pathlib import Path
P=Path('/content/a3_b_1014'); P.mkdir(exist_ok=False)
with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as f:f.extractall(P,filter='data')
(P/'bin').mkdir()
with gzip.open('/content/openfast_5_linux_1014.gz','rb') as f,(P/'bin/openfast').open('wb') as w:shutil.copyfileobj(f,w)
(P/'bin/openfast').chmod(0o755)
r=subprocess.run([str(P/'bin/openfast'),'-v'],capture_output=True,text=True)
print('openfast',r.returncode,(r.stdout+r.stderr)[-1400:])
assert r.returncode==0
sys.path.insert(0,str(P/'code'))
import segment_b_run as b,segment_a_run as a
b.BASE=P/'base';b.ROOT=P/'runs';b.SOURCE_FIELDS=P/'regen';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so'
a.CURVE=P/'base/segment_a_v4_curve.txt'
print('ready',P,'library',b.LIB.exists(),'cpu',os.cpu_count(),flush=True)
