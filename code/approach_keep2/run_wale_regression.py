"""Run real LUW 32x16x20 Poiseuille regression on Colab only."""
from pathlib import Path
import tarfile,subprocess,os
for tag in ('SMAG','WALE'):
 root=Path('/content/reg_'+tag);root.mkdir(exist_ok=False)
 with tarfile.open('/content/'+tag+'_reg_inputs.tar.gz') as t:t.extractall(root,filter='data')
 with open(root/'build.log','w') as f:p=subprocess.run(['make','Linux','-j4'],cwd=root/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 print(tag,'build',p.returncode,flush=True)
 if p.returncode:print((root/'build.log').read_text(errors='replace')[-3000:]);continue
 with open(root/'solver.log','w') as f:p=subprocess.run([str(root/'FluidX3D/bin/FluidX3D')],cwd=root/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 print(tag,'solver',p.returncode,flush=True)
 print('\n'.join(x for x in (root/'solver.log').read_text(errors='replace').splitlines() if 'WALE_FIXTURE' in x)[-2400:],flush=True)
