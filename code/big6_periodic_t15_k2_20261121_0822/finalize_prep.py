#!/usr/bin/env python3
"""Freeze one-group T15 archive and budget using measured 8H A100 throughput."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent;S=R/'pack_stage/periodic_t15_k2/src'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def new(name,text):
 p=R/name
 if p.exists():raise FileExistsError(p)
 p.write_text(text)
source={p.name:sha(p) for p in S.iterdir() if p.is_file()}
arc=R/'t17b_stage.tar.gz';assert not arc.exists();shutil.copy2(R/'stage_big6.tar.gz',arc)
new('t17b_manifest.json',json.dumps({'archive_sha256':sha(arc),'variant_names':{'t15':'periodic_t15_k2'},'variants':{'periodic_t15_k2':source}},indent=2)+'\n')
domain_steps=394900;domain_cu=3.652339;cu_hour=5.4;cap=11.5
rate=domain_steps/(domain_cu*3600/cu_hour)
T=17950;worst=30*T/rate
plan={'steps_per_T':T,'steps_per_second':{'t15':rate},'per_case_overhead_s':350,'fixed_overhead_s':600,'worst_case_solver_s':worst,'reference':'domain8H_20261120_0110 measured 394900 steps / estimated creation-to-release 3.652339 CU; T15 s1 A100, rate conservative inclusive of fixed overhead','single_session_cap_CU':cap,'CU_per_hour':cu_hour,'first_case_upper_CU':(worst+600+180)*cu_hour/3600,'two_case_upper_CU':(2*worst+600+180)*cu_hour/3600}
assert plan['two_case_upper_CU']<cap,plan
new('SESSION_PLAN.json',json.dumps(plan,indent=2)+'\n')
print(json.dumps(plan,indent=2))
