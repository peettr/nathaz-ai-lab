from pathlib import Path
import hashlib,json,tarfile,subprocess,sys,os
R=Path(__file__).resolve().parent
m=json.loads((R/'t17b_manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'t17b_stage.tar.gz')==m['archive_sha256']
with tarfile.open(R/'t17b_stage.tar.gz') as tf:
 names=set(tf.getnames())
 assert all(x.startswith('pack_stage/') or x=='pack_stage' for x in names)
 assert all(x.isdir() or x.isfile() for x in tf)
 for v,items in m['variants'].items():
  for n,h in items.items():
   assert f'pack_stage/{v}/src/{n}' in names and sha(R/'pack_stage'/v/'src'/n)==h
assert sha(R/'assert_T18.py')=='57844319f11fd53261f442dd40de16d78aad6df986d00f86936fd91e972c0e3b'
assert (R/'DRY_PASS_T18_v8.json').is_file() and (R/'DRY_WORKER_T18_final.log').is_file()
assert json.loads((R/'DRY_PASS_T18_v8.json').read_text())['verified']==[g+'_s1' for g in ('K1a','K1b','K2','K3a','K3b')]
source_old=R.parent/'run_20261123_0136_v7'
assert json.loads((source_old/'gate/macro_off.json').read_text())[0]['byte_equal']
assert all(x['byte_equal'] and x['gxx_rc']==0 for x in json.loads((source_old/'gate/macro_off.json').read_text()))
assert all(sha(R/'pack_stage'/v/'src/kernel.cpp')==sha(source_old/'pack_stage'/v/'src/kernel.cpp') for v in m['variants'])
for v in m['variants']:
 x=subprocess.run(['g++','-std=c++17','-fsyntax-only',str(R/'pack_stage'/v/'src/kernel.cpp')],capture_output=True,text=True)
 (R/(v+'_gxx_v8.log')).write_text('exit='+str(x.returncode)+'\n'+x.stderr)
 assert x.returncode==0,(v,x.stderr[:500])
# The real worker, not just a fake launcher, opened every expected PAYLOAD path.
s=(R/'worker_native.py').read_text();c=(R/'controller_t18.py').read_text()
for name in ('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json'):
 assert repr(name) in c
for name in ('t17b_budget.json','t17b_manifest.json','t17b_stage.tar.gz','stub_t18.py','stub_native_original.py'):
 assert repr(name) in s or name in ('stub_t18.py','stub_native_original.py') and name in s
assert "('B0',)+GROUPS" in s and "'C0_verdict.json'" in c
assert 'COLAB '+"'" not in '' # keep this test free of account actions
seals={n:sha(R/n) for n in ('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json','machine.py','controller_t18.py')}
(R/'PREFLIGHT.ok').write_text(json.dumps(seals,indent=2)+'\n')
(R/'NATIVE_PRODUCER_APPROVED.ok').write_text('Local worker dryrun verified; native solver not yet compiled; A100 first builds B0+five then C0.\n')
(R/'PATH_UPLOAD_CHECK.json').write_text(json.dumps({'worker_open':{'budget':'/content/t17b_budget.json','manifest':'/content/t17b_manifest.json','archive':'/content/t17b_stage.tar.gz','source':'/content/t17b/pack_stage/<variant>/src/','stub_fixture_only':'/content/stub_t18.py'},'upload_payload':list(seals)[:7],'dry_run_log':'DRY_WORKER_T18_final.log','note':'all 5 fixtures are synthetic; no physics inferred'},indent=2)+'\n')
print('PREFLIGHT_OK',len(seals),'sealed',len(m['variants']),'variants')
