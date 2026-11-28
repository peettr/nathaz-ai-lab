#!/usr/bin/env python3
"""Freeze one-group archive and conservative one-case CU budget; no GPU."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent
S=R/'pack_stage/periodic_t4/src'
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
new('t17b_manifest.json',json.dumps({'archive_sha256':sha(arc),'variant_names':{'t4':'periodic_t4'},'variants':{'periodic_t4':source}},indent=2)+'\n')
# Domain8H 22T A100 allocation-to-release effective end-to-end rate;
# use it as a conservative floor for an unmeasured first T4 case.
domain_steps=394900;domain_cu=3.652339;cu_hour=5.4
rate=domain_steps/(domain_cu*3600/cu_hour)
T=17950;worst=30*T/rate
plan={'steps_per_T':T,'steps_per_second':{'t4':rate},'per_case_overhead_s':350,'fixed_overhead_s':600,'worst_case_solver_s':worst,'reference':'domain8H_20261120_0110 allocation-to-release 394900 steps / 3.652339 estimated CU; T15 upper-bound proxy; no T4 large-domain rate measured yet','single_session_cap_CU':9,'CU_per_hour':cu_hour,'first_case_upper_CU':(worst+600+180)*cu_hour/3600,'two_case_upper_CU':(2*worst+600+180)*cu_hour/3600}
new('SESSION_PLAN.json',json.dumps(plan,indent=2)+'\n')
assert plan['first_case_upper_CU']<9
print(json.dumps(plan,indent=2))
