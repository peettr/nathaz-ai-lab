from pathlib import Path
import shutil, json, hashlib, tarfile, subprocess
base=Path(__file__).resolve().parent
old=base/'try5'; new=base/'try6'
assert not new.exists()
new.mkdir()
for n in ('EXPERIMENT_CARD.md','SOURCE_DIFF_T3d_to_T4.patch','audit_linked_mirror_final.json','ack_t4.py','check_t4.py','gpu_link_fixture.py','launch_t4.py','controller_t4.py','remote_worker_t4.py'):
    shutil.copy2(old/n,new/n)
shutil.copytree(old/'stage_t4',new/'stage_t4',ignore=shutil.ignore_patterns('temp','bin','RESULTS','__pycache__'))
m=new/'stage_t4/manifest.json'
v=json.loads(m.read_text())
on=new/'stage_t4/FluidX3D_on/src'
# The original source_sha256 referred to try4; on/defines.hpp was modified by the try5 fixture packaging.
for name in v['source_sha256']:
    v['source_sha256'][name]=hashlib.sha256((on/name).read_bytes()).hexdigest()
for fixture,key in [('FluidX3D_gate0','fixture_A_sha256'),('FluidX3D_gate0_B','fixture_B_sha256')]:
    for name,digest in v[key].items():
        assert hashlib.sha256((new/'stage_t4'/fixture/'src'/name).read_bytes()).hexdigest()==digest,(fixture,name)
m.write_text(json.dumps(v,indent=2)+'\n')
c=new/'controller_t4.py'
t=c.read_text().replace('sessions-t4-try5.json','sessions-t4-try6.json').replace('luw-r214a-t4-try5-1116','luw-r214a-t4-try6-1116').replace('T4 try5 #8275f850','T4 try6 #05e26fd2')
assert t!=c.read_text();c.write_text(t)
archive=new/'stage_t4_v2.tar.gz'
with tarfile.open(archive,'w:gz') as f:f.add(new/'stage_t4',arcname='stage_t4')
for variant in ('off','on','gate0','gate0_B'):
    src=new/'stage_t4'/f'FluidX3D_{variant}'/'src'
    fields=v['source_sha256'] if variant=='on' else v['fixture_'+('A' if variant=='gate0' else 'B')+'_sha256'] if variant.startswith('gate0') else {}
    for name,digest in fields.items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==digest
for p in (new/'controller_t4.py',new/'remote_worker_t4.py',new/'launch_t4.py'):
    subprocess.run(['python3','-m','py_compile',str(p)],check=True)
print('TRY6',new,'archive_sha256',hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_hashes_checked')
