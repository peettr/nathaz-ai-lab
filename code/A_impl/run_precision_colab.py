"""Colab-only precision matrix; source staged from the isolated local copy."""
from pathlib import Path
import tarfile, subprocess, hashlib, json, os, time, traceback
r=Path('/content/luw_wp1_precision_v3'); r.mkdir(exist_ok=False)
with tarfile.open('/content/luw_wp1_precision.tar.gz') as a:a.extractall(r,filter='data')
fixture=Path('/content/fixture_fixed.hpp').read_text()
rows=[]
for precision in ['FP32','FP16S','FP16C']:
 for model in (['head','off','first','filtered'] if precision in ('FP32','FP16C') else ['first','filtered']):
  name=precision+'_'+model; target=r/name
  subprocess.run(['cp','-a',str(r/'head' if model=='head' else r/'patched'),str(target)],check=True)
  d=target/'src/defines.hpp'; s=d.read_text().replace('#define FP16C // optional','//#define FP16C // optional')
  s='\n#define WALL_GATE0\n'+ ('#define FP16S\n' if precision=='FP16S' else '#define FP16C\n' if precision=='FP16C' else '') + ('#define GROUND_WALL_MODEL\n' if model in ('first','filtered') else '')+('#define GROUND_WALL_FILTER\n' if model=='filtered' else '')+s
  d.write_text(s)
  setup=target/'src/setup.cpp'; text=setup.read_text(); needle='void main_setup() {'; assert text.count(needle)==1
  setup.write_text(text.replace(needle,fixture+needle,1)+'\n#endif // WALL_GATE0\n')
  env=os.environ.copy();env['LUW_GROUND_ALPHA']='0.2'
  with (target/'build.log').open('w') as f: cp=subprocess.run(['make','Linux','-j4'],cwd=target,stdout=f,stderr=subprocess.STDOUT,timeout=360)
  row={'name':name,'build_rc':cp.returncode,'run_rc':None}
  if cp.returncode==0:
   with (target/'run.log').open('w') as f: cp=subprocess.run([str(target/'bin/FluidX3D')],cwd=target,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
   row['run_rc']=cp.returncode
   row['series']=[line.strip() for line in (target/'run.log').read_text(errors='replace').splitlines() if 'WALL_GATE0 step=' in line]
   row['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.glob('gate0_step_*.bin')}
  rows.append(row);(r/'results.json').write_text(json.dumps(rows,indent=2));print(name,'build',row['build_rc'],'run',row['run_rc'],'series',len(row.get('series',[])),flush=True)
print('RESULTS',str(r/'results.json'),flush=True)
