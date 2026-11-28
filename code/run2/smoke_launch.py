import pathlib,tarfile,hashlib,subprocess,sys,os,json
r=pathlib.Path('/content/t3_run2_smoke');a=pathlib.Path('/content/t3_run2_stage.tar.gz')
assert not r.exists(),'smoke root already exists'
assert hashlib.sha256(a.read_bytes()).hexdigest()=='8c236857af0269fb56491542e202f24b4f6091a2edfc8c09f1bd77ee42c174b4'
r.mkdir()
with tarfile.open(a) as tf:
 for m in tf.getmembers():
  assert (r/m.name).resolve().is_relative_to(r) and not m.issym() and not m.islnk()
 tf.extractall(r,filter='data')
conf=r/'dx1p0_s101/conf.luwpf';old=conf.read_text();assert old.count('run_nstep = 31000')==1
smoke=r/'smoke';smoke.mkdir();(smoke/'proj_temp').mkdir();(smoke/'wind_bc').mkdir()
import shutil
shutil.copyfile(r/'flatground.stl',smoke/'proj_temp/CaseE_PF.stl');shutil.copyfile(r/'dx1p0_s101/wind_bc/profile.dat',smoke/'wind_bc/profile.dat')
(smoke/'conf.luwpf').write_text(old.replace('run_nstep = 31000','run_nstep = 20').replace('purge_avg = 20000','purge_avg = 10').replace('purge_avg_stride = 40','purge_avg_stride = 2'))
worker=r/'smoke_worker.py'
worker.write_text('''import pathlib,subprocess,os,json,time,traceback\nr=pathlib.Path('/content/t3_run2_smoke');out=r/'evidence';out.mkdir(exist_ok=True)\ntry:\n with (out/'build.log').open('w',buffering=1) as f:p=subprocess.run(['make','Linux','-j8'],cwd=r/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=1400)\n assert p.returncode==0,('build',p.returncode)\n binary=r/'FluidX3D/bin/FluidX3D';assert binary.exists()\n env={**os.environ,'LD_LIBRARY_PATH':str(r/'FluidX3D/src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}\n with (out/'solver.log').open('w',buffering=1) as f:p=subprocess.run([str(binary),str(r/'smoke/conf.luwpf')],cwd=r/'smoke',stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,timeout=500)\n (out/'exit.json').write_text(json.dumps({'solver_exit':p.returncode,'solver_log_bytes':(out/'solver.log').stat().st_size}))\nexcept BaseException: (out/'error.log').write_text(traceback.format_exc())\nfinally:(out/'done').write_text('terminal\\n')\n''')
p=subprocess.Popen([sys.executable,'-u',str(worker)],cwd=r,stdout=(r/'worker_console.log').open('w'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
print('SMOKE_LAUNCHED_PID',p.pid,flush=True)
