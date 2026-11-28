from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent;V6=R.parent/'run_20261123_0124_v6'
assert not (R/'pack_stage').exists()
shutil.copytree(V6/'pack_stage',R/'pack_stage')
for v in ('B0','K1a','K1b','K2','K3a','K3b'):
 p=R/'pack_stage'/v/'src/kernel.cpp';s=p.read_text()
 assert s.count(')+"#ifdef WALE_SGS"+R(')==3
 assert s.count(')+"#endif"+R( // WALE_SGS')==3
 s=s.replace(')+"#ifdef WALE_SGS"+R(',')\n#ifdef WALE_SGS\n+R(')
 s=s.replace(')+"#endif"+R( // WALE_SGS',')\n#endif\n+R( // WALE_SGS')
 p.write_text(s)
for n in ('worker_native.py','controller_t18.py','remote_B.py','native_analysis.py','analyze_longspin.py','machine.py','assert_T17.py','assert_T18.py','stub_t18.py','stub_native_original.py','dry_check_t18_v2.py'):
 shutil.copyfile(V6/n,R/n)
# The copied dryrun references its own root, not an old stage.
p=R/'dry_check_t18_v2.py';s=p.read_text().replace('dry_content_t18_v2','dry_content_t18_v7').replace('DRY_WORKER_T18_v2.log','DRY_WORKER_T18_v7.log').replace('DRY_PASS_T18.json','DRY_PASS_T18_v7.json');p.write_text(s)
archive=R/'t17b_stage.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
variants={v:{p.name:sha(p) for p in (R/'pack_stage'/v/'src').iterdir() if p.is_file()} for v in ('B0','K1a','K1b','K2','K3a','K3b')}
(R/'t17b_manifest.json').write_text(json.dumps({'archive_sha256':sha(archive),'variant_names':{v:v for v in variants},'variants':variants},indent=2)+'\n')
print('v7 generated',sha(archive))
