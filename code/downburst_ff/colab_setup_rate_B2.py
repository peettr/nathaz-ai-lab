"""Bootstrap an isolated A3-B2 Colab directory; no solver here."""
from pathlib import Path
import tarfile,gzip,shutil,subprocess,os,json
P=Path('/content/a3_b2_1014');P.mkdir(exist_ok=False)
with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as f:f.extractall(P/'a3_b_1014',filter='data')
with tarfile.open('/content/rosco210_ff_src_rate_B2.tar.gz') as f:f.extractall(P,filter='data')
(P/'bin').mkdir()
for name in ('openfast_5_linux_1014','turbsim_5_linux_B2'):
 with gzip.open('/content/'+name+'.gz','rb') as f,(P/'bin'/name.split('_')[0]).open('wb') as out:shutil.copyfileobj(f,out)
 (P/'bin'/name.split('_')[0]).chmod(0o755)
shutil.copyfile('/content/TurbSim_template_B2.inp',P/'TurbSim_template_B2.inp')
cmd=['cmake','-S',str(P/'rosco210_ff_src_rate_B2'),'-B',str(P/'rosco210_ff_build_rate_B2'),'-DCMAKE_BUILD_TYPE=Release']
with (P/'build_B2.log').open('w') as f:
 r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode==0:r=subprocess.run(['cmake','--build',str(P/'rosco210_ff_build_rate_B2'),'-j','4'],stdout=f,stderr=subprocess.STDOUT)
print('BUILD_RC',r.returncode,'LOG_TAIL',(P/'build_B2.log').read_text()[-2600:],flush=True)
assert r.returncode==0
print('BINARY',P/'rosco210_ff_build_rate_B2/libdiscon.so','size',(P/'rosco210_ff_build_rate_B2/libdiscon.so').stat().st_size,flush=True)
