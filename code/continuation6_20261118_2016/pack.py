import hashlib,json,pathlib,tarfile,shutil,difflib
R=pathlib.Path(__file__).resolve().parent
OLD=R.parent/'continuation5_20261118_200219'
for n in ('worker_full.py','controller_full.py','remote_io_full.py','remote_worker_run2.py','machine.py','stub_full.py','dry_e3.py'):
 shutil.copyfile(OLD/n,R/n)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with tarfile.open(OLD/'t15_stage.tar.gz') as t:
 orig=t.extractfile('stage/FluidX3D_e3/src/setup.cpp').read().decode()
new=(R/'stage/FluidX3D_e3/src/setup.cpp').read_text()
(R/'E3prime_setup.diff').write_text(''.join(difflib.unified_diff(orig.splitlines(True),new.splitlines(True),fromfile='continuation5/e3/setup.cpp',tofile='continuation6/e3/setup.cpp')))
with tarfile.open(R/'t15_stage.tar.gz','w:gz') as t:t.add(R/'stage',arcname='stage')
man=json.loads((OLD/'t15_manifest.json').read_text());man['archive_sha256']=sha(R/'t15_stage.tar.gz');man['sources']['e3']['setup.cpp']=sha(R/'stage/FluidX3D_e3/src/setup.cpp')
(R/'t15_manifest.json').write_text(json.dumps(man,indent=2)+'\n')
print('PACKED',man['archive_sha256'],'SETUP',man['sources']['e3']['setup.cpp'])
