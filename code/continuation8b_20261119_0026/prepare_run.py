#!/usr/bin/env python3
"""Seal a new E3-only payload while retaining prior immutable members."""
import hashlib,io,json,pathlib,shutil,tarfile
R=pathlib.Path(__file__).resolve().parent
P=R.parent/'continuation7_20261118_231514'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
for n in ('assert_e3prime.py','controller_full.py','stub_full.py','machine.py','remote_io_full.py','remote_worker_run2.py','worker_full.py'):
 a=R/n;b=P/n
 assert a.is_file() and sha(a)==sha(b),(n,'unexpected change')
old=json.loads((P/'t15_manifest.json').read_text());new=json.loads(json.dumps(old))
for n in ('kernel.cpp','defines.hpp'):
 p=R/'stage/FluidX3D_e3/src'/n
 assert p.is_file()
 new['sources']['e3'][n]=sha(p)
for v in ('off','on','k3'):
 for n,h in old['sources'][v].items():
  assert sha(R/'stage'/('FluidX3D_'+v)/'src'/n)==h,(v,n)
for n,h in old['cases'].items(): assert sha(R/'stage'/n/'conf.luwpf')==h,n
old_tar=P/'t15_stage.tar.gz';new_tar=R/'t15_stage.tar.gz'
with tarfile.open(old_tar,'r:gz') as src,tarfile.open(new_tar,'x:gz') as dst:
 for member in src:
  if member.isfile():
   if member.name in ('stage/FluidX3D_e3/src/kernel.cpp','stage/FluidX3D_e3/src/defines.hpp'):
    p=R/member.name;member.size=p.stat().st_size
    with p.open('rb') as f:dst.addfile(member,f)
   else:dst.addfile(member,src.extractfile(member))
  else:dst.addfile(member)
new['archive_sha256']=sha(new_tar)
(R/'t15_manifest.json').write_text(json.dumps(new,sort_keys=True,indent=2)+'\n')
print('archive_sha256',new['archive_sha256'],'old',old['archive_sha256'])
print('new e3 kernel',new['sources']['e3']['kernel.cpp'],'defines',new['sources']['e3']['defines.hpp'])
