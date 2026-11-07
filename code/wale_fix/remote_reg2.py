from pathlib import Path
import tarfile,subprocess
r=Path('/content/luw_wale_floor_reg2');r.mkdir(exist_ok=False)
with tarfile.open('/content/floor_reg2_inputs.tar.gz') as t:t.extractall(r,filter='data')
with (r/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-j4'],cwd=r/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=800)
print('BUILD',p.returncode,flush=True)
if p.returncode:print((r/'build.log').read_text()[-3000:],flush=True)
else:
 with (r/'solver.log').open('w') as f:p=subprocess.run([str(r/'FluidX3D/bin/FluidX3D')],cwd=r/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 print('EXIT',p.returncode,flush=True)
 print('\n'.join(x for x in (r/'solver.log').read_text(errors='replace').splitlines() if 'WALE_FIXTURE' in x)[-1200:],flush=True)
