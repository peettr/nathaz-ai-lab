#!/usr/bin/env python3
"""Read-only frozen-package audit and exclusive preallocation readiness seal."""
from pathlib import Path
import json,hashlib,tarfile,sys,datetime,zoneinfo
R=Path(__file__).resolve().parent;src=R/'pack_stage/periodic_t15_k2/src'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
m=json.loads((R/'t17b_manifest.json').read_text());p=json.loads((R/'SESSION_PLAN.json').read_text())
assert sha(R/'t17b_stage.tar.gz')==m['archive_sha256']
assert set(m['variants'])=={'periodic_t15_k2'} and m['variant_names']=={'t15':'periodic_t15_k2'}
assert all(sha(src/n)==h for n,h in m['variants']['periodic_t15_k2'].items())
assert all((R/n).is_file() for n in ('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','machine.py','DRY_PASS_T15.json','DRY_WORKER_T15_v1.log'))
assert json.loads((R/'DRY_PASS_T15.json').read_text())['verified']==['t15_s1','t15_s2']
assert p['two_case_upper_CU']<11.5 and p['steps_per_T']==17950
w=(R/'worker_native.py').read_text(); c=(R/'controller_native.py').read_text(); a=(R/'native_analysis.py').read_text()
assert "GROUPS=('t15',)" in w and "order=(('t15','1'),('t15','2'))" in w
assert "ALL_CASES=('t15_s1','t15_s2')" in c and 'cap=11.5' in c and "'--max-hours','3'" in c
assert 'NX,NY,NZ=(int(os.environ.get(\'T17_TEST_NX\',512)),int(os.environ.get(\'T17_TEST_NY\',256)),64)' in a
assert 'seed_metrics(' not in w and 'assert_T17(' not in w
ref=R.parent/'domain8H_20261120_0110/pack_stage/periodic_t15_k2/src'
assert all(sha(src/n)==sha(ref/n) for n in ('kernel.cpp','lbm.cpp','defines.hpp','setup.cpp'))
seal={n:sha(R/n) for n in ('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json','machine.py','controller_native.py')}
expected_seal=json.dumps({n:seal[n] for n in ('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json','machine.py')},indent=2)+'\n'
if (R/'PREFLIGHT.ok').exists(): assert (R/'PREFLIGHT.ok').read_text()==expected_seal
else: (R/'PREFLIGHT.ok').open('x').write(expected_seal)
producer_text='T15 k2 native statistical producer; source and dry-run checked; solver not exercised locally\n'
if (R/'NATIVE_PRODUCER_APPROVED.ok').exists():assert (R/'NATIVE_PRODUCER_APPROVED.ok').read_text()==producer_text
else:(R/'NATIVE_PRODUCER_APPROVED.ok').open('x').write(producer_text)
report={'source_manifest':json.loads((R/'manifest_big6.json').read_text())['source_files'],'archive_sha256':m['archive_sha256'],'local_dry_run':json.loads((R/'DRY_PASS_T15.json').read_text()),'session_plan':p,'seal':seal,'limitations':['Local dry run stubs solver; native GPU compile and run remain to be verified','T4 peer root is active and untouched']}
(R/'PREFLIGHT_REPORT.json').open('x').write(json.dumps(report,indent=2)+'\n')
print('PREFLIGHT_PASS',json.dumps({'archive':m['archive_sha256'],'cases':report['local_dry_run']['verified'],'upper_CU':p['two_case_upper_CU']}))
