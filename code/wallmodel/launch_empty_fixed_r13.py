"""Compile corrected Case-E wall index and run a fresh, separate empty case."""
from pathlib import Path
import tarfile,subprocess,time,shutil
r=Path('/content/luw_wall_empty_r13');src=r/'solver_onfixed';assert not src.exists();src.mkdir()
with tarfile.open('/content/luw_wall_empty_fixed_r13.tar.gz') as tar:tar.extractall(src,filter='data')
source=src/'FluidX3D';p=source/'src/defines.hpp';text=p.read_text();assert text.count('//#define GROUND_WALL_MODEL')==1;p.write_text(text.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL'))
with (r/'build_onfixed.log').open('w') as out:cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=300)
print('BUILD_FIXED',cp.returncode,flush=True);assert cp.returncode==0
case=r/'case_onfixed';(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
base=r/'case_on'
for rel in ('conf.luwpf','wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):shutil.copy2(base/rel,case/rel)
assert not (r/'onfixed.exit').exists();(r/'onfixed.lock').open('x').close()
code='''from pathlib import Path
import subprocess,time
r=Path('/content/luw_wall_empty_r13');t=time.monotonic();case=r/'case_onfixed';exe=r/'solver_onfixed/FluidX3D/bin/FluidX3D'
with (r/'solver_onfixed.log').open('w',buffering=1) as out:
 p=subprocess.Popen([str(exe),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
 p.wait();(r/'onfixed.exit').write_text(f'exit={p.returncode} wall_s={time.monotonic()-t:.2f}\\n')
'''
script=r/'wrapper_onfixed.py';script.write_text(code)
with (r/'wrapper_onfixed.log').open('w') as out:proc=subprocess.Popen(['python3',str(script)],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED_FIXED',proc.pid,flush=True)
