import os,pathlib,hashlib,tarfile,subprocess,sys,json
root=pathlib.Path('/content/t3_t3b_stage');archive=pathlib.Path('/content/t3_t3b_bundle.tar.gz')
expected=os.environ['T3_BUNDLE_SHA']
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
assert not root.exists(),'t3b stage already exists; do not relaunch'
root.mkdir()
with tarfile.open(archive) as tf:
 for m in tf.getmembers():assert (root/m.name).resolve().is_relative_to(root) and not m.issym() and not m.islnk()
 tf.extractall(root,filter='data')
(root/'remote_worker_run2.py').write_bytes(pathlib.Path('/content/t3_run2_parser.py').read_bytes())
(root/'remote_worker_t3b.py').write_bytes(pathlib.Path('/content/t3_t3b_worker.py').read_bytes())
man=json.loads((root/'stage_manifest.json').read_text());H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,key in [('setup.cpp','setup_sha256'),('defines.hpp','defines_sha256')]:assert H(root/'FluidX3D/src'/name)==man[key]
for case,v in man['cases'].items():assert H(root/case/'conf.luwpf')==v['conf_sha256']
out=pathlib.Path('/content/t3_t3b_out');assert not out.exists()
p=subprocess.Popen([sys.executable,'-u',str(root/'remote_worker_t3b.py')],cwd=root,env=os.environ,stdin=subprocess.DEVNULL,stdout=(root/'t3b.log').open('x'),stderr=subprocess.STDOUT,start_new_session=True)
(root/'launch.pid').write_text(str(p.pid)+'\n');print('T3B_LAUNCHED_PID',p.pid,flush=True)
