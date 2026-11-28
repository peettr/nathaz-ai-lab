from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
shutil.copyfile(R/'worker_t18.py',R/'worker_native.py')
OLD=R.parents[2]/'R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455'
shutil.copyfile(OLD/'stub_native.py',R/'stub_native_original.py')
archive=R/'t17b_stage.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
variants={v:{p.name:sha(p) for p in (R/'pack_stage'/v/'src').iterdir() if p.is_file()} for v in ('B0','K1a','K1b','K2','K3a','K3b')}
m={'archive_sha256':sha(archive),'variant_names':{v:v for v in variants},'variants':variants}
(R/'t17b_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print('archive',archive.stat().st_size,sha(archive),'files',sum(map(len,variants.values())))
