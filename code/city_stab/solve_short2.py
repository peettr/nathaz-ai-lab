from pathlib import Path
import subprocess,os,time
R=Path('/content/luw_citystab_short_v2')
env=os.environ.copy();env['LUW_GROUND_MIX_A']='0.0'
f=(R/'solver2.log').open('w',buffering=1)
p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(R/'case/conf.luwpf')],cwd=R/'case',env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
start=time.time()
while p.poll() is None:
 time.sleep(20)
 print('SOLVER_ELAPSED',round(time.time()-start), 'STATUS',p.poll(),flush=True)
 if time.time()-start>1400:p.kill();break
(R/'exit2.txt').write_text(str(p.wait()))
print('SOLVER_EXIT',p.returncode, 'LOG_TAIL', (R/'solver2.log').read_text()[-1600:])
print('TRACE_TAIL',(R/'case/RESULTS/city_stability.csv').read_text()[-1600:] if (R/'case/RESULTS/city_stability.csv').exists() else 'MISSING')
