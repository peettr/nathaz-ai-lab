# Build and run only native Case E voxel initialization on A100.
from pathlib import Path
import tarfile,subprocess,numpy as np,time
root=Path('/content/step4_init_v2');root.mkdir(exist_ok=True)
with tarfile.open('/content/step4_init_stage_v2.tar.gz') as t:t.extractall(root,filter='data')
with (root/'build.log').open('w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root/'FluidX3D',stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join((root/'build.log').read_text().splitlines(True)[-30:]));raise SystemExit(1)
with (root/'init.log').open('w') as f:r=subprocess.run([str(root/'FluidX3D/bin/FluidX3D'),str(root/'case/conf.luwpf')],cwd=root/'case',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=180)
print('INIT',r.returncode,flush=True)
if r.returncode:print(''.join((root/'init.log').read_text().splitlines(True)[-30:]));raise SystemExit(2)
p=root/'case/RESULTS/native_flags_z0_90.bin';print('RAW',p.exists(),p.stat().st_size if p.exists() else 0,flush=True)
a=np.fromfile(p,dtype=np.uint8);assert a.size==91*500*500,a.size
np.savez_compressed('/content/step4_flags_z0_90.npz',flags=a.reshape(91,500,500))
print('NPZ',Path('/content/step4_flags_z0_90.npz').stat().st_size,flush=True)
Path('/content/step4_init.done').write_text('done')
