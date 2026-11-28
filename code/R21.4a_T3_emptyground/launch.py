import os,pathlib,hashlib,tarfile,subprocess,sys
root=pathlib.Path('/content/t3_stage'); archive=pathlib.Path('/content/stage_bundle.tar.gz')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='131d2d35fa4b8530f9b0e7fdf9292e879f724844b0bed0d5772517300a0578ca'
assert not root.exists(),'T3 stage already exists; do not relaunch'
root.mkdir()
with tarfile.open(archive) as tf:
 for m in tf.getmembers():
  target=(root/m.name).resolve();assert target.is_relative_to(root) and not m.issym() and not m.islnk()
 tf.extractall(root,filter='data')
(root/'remote_worker.py').write_bytes(pathlib.Path('/content/remote_worker.py').read_bytes())
for n,h in [('setup.cpp','9c5e0d2c0cc5cf129c7dc1b018139e04b70e4e0cac8dc5bb8354d1a0dc33aac1'),('defines.hpp','cb1009f00376f9d9d51114473a6673516be1f594874c1347c08152e3d9448ac3')]:
 p=root/'FluidX3D/src'/n;assert hashlib.sha256(p.read_bytes()).hexdigest()==h
out=pathlib.Path('/content/t3_out');out.mkdir(exist_ok=True)
(out/'run.log').write_text('LAUNCH_PREPARED\n')
p=subprocess.Popen([sys.executable,'-u',str(root/'remote_worker.py')],cwd=root,env={**os.environ,'T3_DEADLINE':os.environ['T3_DEADLINE'],'T3_RATE':os.environ['T3_RATE']},stdin=subprocess.DEVNULL,stdout=(out/'run.log').open('a'),stderr=subprocess.STDOUT,start_new_session=True)
(root/'launch.pid').write_text(str(p.pid)+'\n')
print('LAUNCHED_PID',p.pid,flush=True)
