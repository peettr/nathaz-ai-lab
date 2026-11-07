#!/usr/bin/env python3
"""Build and run solver only; postprocessing is a separately registered job."""
import os,pathlib,subprocess,sys,time
r=pathlib.Path(sys.argv[1]);case=r/'case_4gpu';base=r/'FluidX3D'
print('START',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
with (r/'build.log').open('w') as out:
    p=subprocess.run(['make','Linux','-j8'],cwd=base,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1200)
(r/'build.exitcode').write_text(str(p.returncode)+'\n')
if p.returncode: raise SystemExit(p.returncode)
print('BUILD_OK',flush=True)
env={**os.environ,'LD_LIBRARY_PATH':str(base/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
with (r/'solver.log').open('w') as out:
    p=subprocess.run([str(base/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env)
(r/'solver.exitcode').write_text(str(p.returncode)+'\n')
print('SOLVER_EXIT',p.returncode,flush=True)
print('FINISH',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
raise SystemExit(p.returncode)
