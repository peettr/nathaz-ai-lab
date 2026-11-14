from pathlib import Path
import tarfile,subprocess,hashlib,json,os
r=Path('/content/luw_wp1_precision_extra');r.mkdir(exist_ok=False)
with tarfile.open('/content/luw_wp1_precision.tar.gz') as t:t.extractall(r,filter='data')
fixture=Path('/content/fixture_fixed.hpp').read_text()
rows=[]
for name,precision,tau in [('FP32_zero','FP32','0.0f'),('FP16C_constant','FP16C','5.0e-5f')]:
 target=r/name;subprocess.run(['cp','-a',str(r/'patched'),str(target)],check=True)
 p=target/'src/defines.hpp';s=p.read_text().replace('#define FP16C // optional','//#define FP16C // optional');p.write_text('#define WALL_GATE0\n#define GROUND_WALL_MODEL\n'+('#define FP16C\n' if precision=='FP16C' else '')+s)
 p=target/'src/setup.cpp';s=p.read_text();assert s.count('void main_setup() {')==1;p.write_text(s.replace('void main_setup() {',fixture+'void main_setup() {',1)+'\n#endif // WALL_GATE0\n')
 p=target/'src/kernel.cpp';s=p.read_text();needle='const float tau=rhon*sq(def_ground_kappa*um/logwall);';assert s.count(needle)==1;p.write_text(s.replace(needle,'const float tau='+tau+';'))
 with (target/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=target,stdout=f,stderr=subprocess.STDOUT,timeout=360)
 row={'name':name,'build_rc':b.returncode};
 if b.returncode==0:
  with (target/'run.log').open('w') as f:p=subprocess.run([str(target/'bin/FluidX3D')],cwd=target,env={**os.environ,'LUW_GROUND_ALPHA':'0.2'},stdout=f,stderr=subprocess.STDOUT,timeout=300)
  row.update(run_rc=p.returncode,series=[x for x in (target/'run.log').read_text(errors='replace').splitlines() if 'WALL_GATE0 step=' in x]);row['hashes']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in target.glob('gate0_step_*.bin')}
 rows.append(row);(r/'results.json').write_text(json.dumps(rows,indent=2));print(name,row['build_rc'],row.get('run_rc'),len(row.get('series',[])),flush=True)
