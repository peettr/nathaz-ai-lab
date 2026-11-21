from pathlib import Path
import shutil,subprocess,os
r=Path('/content/luw_wp1_a_v1')
c=r/'case_smoke';shutil.copytree(r/'case',c,dirs_exist_ok=False)
p=c/'conf.luwpf';s=p.read_text();assert s.count('run_nstep = 31000')==1;s=s.replace('run_nstep = 31000','run_nstep = 10');s=s.replace('purge_avg = 20000','purge_avg = 0');p.write_text(s)
log=(r/'smoke.log').open('w')
with (r/'smoke_runner.py').open('w') as f:f.write("import subprocess,pathlib,os\nr=pathlib.Path('/content/luw_wp1_a_v1'); c=r/'case_smoke'; e=os.environ.copy(); e['LUW_GROUND_ALPHA']='0.2'\np=subprocess.run([str(r/'FluidX3D/bin/FluidX3D'),str(c/'conf.luwpf')],cwd=c,stdin=subprocess.DEVNULL,stdout=(r/'smoke_solver.log').open('w'),stderr=subprocess.STDOUT,env=e)\n(r/'smoke.rc').write_text(str(p.returncode))\n(r/'smoke.done').write_text('done')\n")
p=subprocess.Popen(['python3',str(r/'smoke_runner.py')],cwd=r,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
print('SMOKE PID',p.pid,flush=True)
