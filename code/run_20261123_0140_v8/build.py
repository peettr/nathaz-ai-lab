from pathlib import Path
import shutil,tarfile,json,hashlib
R=Path(__file__).resolve().parent;V=R.parent/'run_20261123_0136_v7'
assert not (R/'pack_stage').exists();shutil.copytree(V/'pack_stage',R/'pack_stage')
for n in ('worker_native.py','controller_t18.py','remote_B.py','native_analysis.py','analyze_longspin.py','machine.py','assert_T17.py','assert_T18.py','stub_t18.py','stub_native_original.py','dry_check_t18_v2.py','gate_sources.py'):
 shutil.copyfile(V/n,R/n)
for v in ('B0','K1a','K1b','K2','K3a','K3b'):
 p=R/'pack_stage'/v/'src/t17_b_native.inc';s=p.read_text()
 assert s.count('const ulong sample_stride=(mode=="smoke")?100ul:200ul;')==1
 s=s.replace('const ulong sample_stride=(mode=="smoke")?100ul:200ul;','const ulong sample_stride=(mode=="smoke")?1000ul:200ul;')
 s=s.replace('const ulong ledger_stride=(mode=="smoke")?50ul:100ul;','const ulong ledger_stride=(mode=="smoke")?1000ul:100ul;')
 s=s.replace('capture(step%sample_stride==0ul);','capture(mode!="smoke" && step%sample_stride==0ul);')
 p.write_text(s)
p=R/'dry_check_t18_v2.py';s=p.read_text().replace('dry_content_t18_v7','dry_content_t18_v8').replace('DRY_WORKER_T18_v7.log','DRY_WORKER_T18_v8.log').replace('DRY_PASS_T18_v7.json','DRY_PASS_T18_v8.json');p.write_text(s)
archive=R/'t17b_stage.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
variants={v:{p.name:sha(p) for p in (R/'pack_stage'/v/'src').iterdir() if p.is_file()} for v in ('B0','K1a','K1b','K2','K3a','K3b')}
(R/'t17b_manifest.json').write_text(json.dumps({'archive_sha256':sha(archive),'variant_names':{v:v for v in variants},'variants':variants},indent=2)+'\n')
print('v8 stage',sha(archive))
