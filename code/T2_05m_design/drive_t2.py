#!/usr/bin/env python3
"""Run fine grid only after Slurm afterok dependency on T1c2."""
import json,os,pathlib,subprocess,sys,time
r=pathlib.Path(sys.argv[1]);case=r/'case_4gpu';base=r/'FluidX3D'
print('START',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
with (r/'build.log').open('w') as out:
 p=subprocess.run(['make','Linux','-j8'],cwd=base,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1200)
assert p.returncode==0,('build',p.returncode)
print('BUILD_OK',flush=True)
env={**os.environ,'LD_LIBRARY_PATH':str(base/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
with (r/'solver.log').open('w') as out:
 p=subprocess.run([str(base/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env)
(r/'solver.exitcode').write_text(str(p.returncode)+'\n')
print('SOLVER_EXIT',p.returncode,flush=True);assert p.returncode==0
with (r/'extract.log').open('w') as out:
 e=subprocess.run([sys.executable,str(r/'extract_t2.py'),str(r)],stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1800)
print('EXTRACT_EXIT',e.returncode,flush=True);assert e.returncode==0
result=json.loads((r/'points_80_t2.json').read_text())
print('MAE',result['mae'],'DELTA_MAE',result['delta_mae'],flush=True)
print('FINISH',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
