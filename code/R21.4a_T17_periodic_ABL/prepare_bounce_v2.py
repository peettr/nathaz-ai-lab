#!/usr/bin/env python3
"""Construct bounce-only package in a fresh root without altering evidence."""
from pathlib import Path
import datetime, shutil, hashlib, json, tarfile, difflib, math
base=Path(__file__).resolve().parent
old=base/'big6_periodic_bounce_20261121_073425'
t4=base/'big6_periodic_t4_20261121_0800'
root=base/('big6_periodic_bounce_v2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
root.mkdir(exist_ok=False)
for name in ('worker_native.py','controller_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','machine.py','stub_native.py'):
    source=old/name if (old/name).exists() else t4/name
    shutil.copy2(source,root/name)
shutil.copytree(old/'pack_stage',root/'pack_stage')
# The bounce producer was already dimensioned and 25T staged in old root; never rerun its destructive preparation.
src=root/'pack_stage/periodic_bounce/src'
assert 'LBM lbm(512u,256u,66u' in (src/'setup.cpp').read_text()
assert '25ul*Tsteps' in (src/'t17_b_native.inc').read_text()
# Use the tested native analyzer/worker/controller layout from T4, specialized to bounce.
for name in ('native_analysis.py','analyze_longspin.py','worker_native.py','controller_native.py'):
    shutil.copy2(t4/name,root/name)
p=root/'worker_native.py'; s=p.read_text(); before=s
s=s.replace("GROUPS=('t4',);SEEDS=('1','2')","GROUPS=('bounce',);SEEDS=('1','2')")
s=s.replace("order=(('t4','1'),('t4','2'))","order=(('bounce','1'),('bounce','2'))")
s=s.replace("(('t15',) if mode=='smoke' else GROUPS)","GROUPS")
assert s!=before and "order=(('bounce','1'),('bounce','2'))" in s
p.write_text(s)
p=root/'controller_native.py';s=p.read_text();before=s
s=s.replace("ALL_CASES=('t4_s1','t4_s2')","ALL_CASES=('bounce_s1','bounce_s2')")
s=s.replace("cap=9.0","cap=12.5")
s=s.replace("9*3600/RATE","12.5*3600/RATE")
s=s.replace("if plan['worst_case_solver_s']+plan['fixed_overhead_s']+180 >= 12.5*3600/RATE:","if 2*plan['worst_case_solver_s']+plan['fixed_overhead_s']+180 >= 12.5*3600/RATE:")
s=s.replace("'--max-hours','2','--expect-hours','2'","'--max-hours','4','--expect-hours','4'")
assert s!=before
p.write_text(s)
# Avoid hashing multi-GB input: sealed stage is small (~MB); include all source hashes in manifest.
with tarfile.open(root/'t17b_stage.tar.gz','w:gz') as tar:tar.add(root/'pack_stage',arcname='pack_stage')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
files={p.name:sha(p) for p in src.iterdir() if p.is_file()}
manifest={'archive_sha256':sha(root/'t17b_stage.tar.gz'),'variant_names':{'bounce':'periodic_bounce'},'variants':{'periodic_bounce':files}}
(root/'t17b_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Rate is based on the measured big-domain T15 22T session, conservative relative to stage A bounce.
rate=162.18374033735643
T=17950
worst=30*T/rate
plan={'steps_per_T':T,'steps_per_second':{'bounce':rate},'per_case_overhead_s':220,'fixed_overhead_s':420,'worst_case_solver_s':worst,'reference':'domain8H_20261120_0110 22T allocation-to-release proxy 162.18 steps/s; each case rechecks observed rate','single_session_cap_CU':12.5,'CU_per_hour':5.4}
(root/'SESSION_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
(root/'SOURCE_SHA256.json').write_text(json.dumps({'archive':manifest['archive_sha256'],'source_files':files},indent=2)+'\n')
(root/'DIFF_FROM_T4.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='t4/controller_native.py',tofile='bounce/controller_native.py')))
print(root)
print('archive',manifest['archive_sha256'])
print('worst_case_s',worst,'two_cases_upper_s',2*(worst+220)+420+180,'cap_s',12.5*3600/5.4)
