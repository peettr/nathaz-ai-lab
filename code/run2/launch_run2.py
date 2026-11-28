import os,pathlib,hashlib,tarfile,subprocess,sys,json
root=pathlib.Path('/content/t3_run2_stage');archive=pathlib.Path('/content/t3_run2_bundle.tar.gz')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='a07d35a0b1eb6bb2b8e79762766f6de72e4e4ba1701db2a12384ac9f0132099d'
assert not root.exists(),'run2 stage already exists; do not relaunch'
root.mkdir()
with tarfile.open(archive) as tf:
 for m in tf.getmembers():
  assert (root/m.name).resolve().is_relative_to(root) and not m.issym() and not m.islnk()
 tf.extractall(root,filter='data')
(root/'remote_worker.py').write_bytes(pathlib.Path('/content/t3_run2_worker.py').read_bytes())
manifest=json.loads((root/'stage_manifest.json').read_text())
for name,key in [('setup.cpp','setup_sha256'),('defines.hpp','defines_sha256')]:
 assert hashlib.sha256((root/'FluidX3D/src'/name).read_bytes()).hexdigest()==manifest[key]
for case,v in manifest['cases'].items():assert hashlib.sha256((root/case/'conf.luwpf').read_bytes()).hexdigest()==v['conf_sha256']
out=pathlib.Path('/content/t3_run2_out');out.mkdir(exist_ok=False)
(out/'run.log').write_text('RUN2_LAUNCH_PREPARED\n')
p=subprocess.Popen([sys.executable,'-u',str(root/'remote_worker.py')],cwd=root,env={**os.environ,'T3_DEADLINE':os.environ['T3_DEADLINE'],'T3_RATE':os.environ['T3_RATE']},stdin=subprocess.DEVNULL,stdout=(out/'run.log').open('a'),stderr=subprocess.STDOUT,start_new_session=True)
(root/'launch.pid').write_text(str(p.pid)+'\n');print('RUN2_LAUNCHED_PID',p.pid,flush=True)
