#!/usr/bin/env python3
"""Copy the read-only validated T4 orchestration into an isolated T15 k2 root."""
from pathlib import Path
import shutil,json
R=Path(__file__).resolve().parent; T4=R.parent/'big6_periodic_t4_20261121_0800'
for n in ('native_analysis.py','analyze_longspin.py','assert_T17.py','remote_B.py','machine.py','stub_native.py','dry_run.py','dry_check.py','worker_native.py','controller_native.py'):
 p=R/n
 assert not p.exists(),n
 s=(T4/n).read_text()
 if n=='worker_native.py':
  for old,new in (("GROUPS=('t4',);SEEDS=('1','2')","GROUPS=('t15',);SEEDS=('1','2')"),("order=(('t4','1'),('t4','2'))","order=(('t15','1'),('t15','2'))")):
   assert s.count(old)==1,(n,old);s=s.replace(old,new)
 if n=='controller_native.py':
  for old,new in (("ALL_CASES=('t4_s1','t4_s2')","ALL_CASES=('t15_s1','t15_s2')"),('9*3600/RATE','11.5*3600/RATE'),('cap=9.0','cap=11.5')):
   assert s.count(old)==1,(n,old);s=s.replace(old,new)
 if n=='dry_check.py':
  for old,new in (('dry_content_t4_v4','dry_content_t15_v1'),("('t4_s1','t4_s2')","('t15_s1','t15_s2')"),("{'t4':162}","{'t15':162}"),('DRY_WORKER_T4_v4.log','DRY_WORKER_T15_v1.log'),('DRY_PASS_T4.json','DRY_PASS_T15.json'),('DRY_PASS_T4','DRY_PASS_T15')):
   assert old in s,(n,old);s=s.replace(old,new)
 p.write_text(s)
# Stub is identical and takes seed from environment; no physical results.
print('copied orchestration', [x.name for x in R.iterdir() if x.is_file()])
