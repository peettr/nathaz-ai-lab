"""Single-A100 isolated gate-0 build/execute; never run on 工作站."""
from pathlib import Path
import tarfile, subprocess, hashlib, json, os, time
r=Path('/content/luw_wp1_gate0_1015_u012'); r.mkdir(exist_ok=False)
with tarfile.open('/content/luw_wp1_gate0_stage_u012.tar.gz') as a:a.extractall(r,filter='data')
fixture=(r/'gate0_fixture.hpp').read_text()
results=[]
for name,source,model,filter_on,zero in [('head','head',False,False,False),('off','patched',False,False,False),('zero','patched',True,False,True),('force','patched',True,True,False)]:
    target=r/(name+'_run'); subprocess.run(['cp','-a',str(r/source),str(target)],check=True)
    d=target/'src/defines.hpp'; s=d.read_text();s='\n#define WALL_GATE0\n'+s
    if model:s='\n#define GROUND_WALL_MODEL\n'+s
    if filter_on:s='\n#define GROUND_WALL_FILTER\n'+s
    d.write_text(s)
    setup=target/'src/setup.cpp'; text=setup.read_text(); needle='void main_setup() {'; assert text.count(needle)==1
    setup.write_text(text.replace(needle,fixture+needle,1)+'\n#endif // WALL_GATE0\n')
    if zero:
        p=target/'src/kernel.cpp';s=p.read_text(); needle='const float tau=rhon*sq(def_ground_kappa*um/logwall);';assert s.count(needle)==1;p.write_text(s.replace(needle,'const float tau=0.0f; // fixture zero-force'))
    env=os.environ.copy();env['LUW_GROUND_ALPHA']='0.2'
    with (target/'build.log').open('w') as f: cp=subprocess.run(['make','Linux','-j4'],cwd=target,stdout=f,stderr=subprocess.STDOUT,timeout=300)
    result={'name':name,'build_rc':cp.returncode,'run_rc':None}
    if cp.returncode==0:
        with (target/'run.log').open('w') as f: cp=subprocess.run([str(target/'bin/FluidX3D')],cwd=target,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240)
        result['run_rc']=cp.returncode
        result['series']=[line.strip() for line in (target/'run.log').read_text(errors='replace').splitlines() if 'WALL_GATE0 step=' in line]
        result['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.glob('gate0_step_*.bin')}
    results.append(result);(r/'results.json').write_text(json.dumps(results,indent=2));print(name,'build',result['build_rc'],'run',result['run_rc'],'series',len(result.get('series',[])),flush=True)
    if result['build_rc'] or result['run_rc']:break
print('RESULTS',str(r/'results.json'),flush=True)
