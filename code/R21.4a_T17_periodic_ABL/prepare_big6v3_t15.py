#!/usr/bin/env python3
"""Stage a new immutable T15 big-domain payload; never edit predecessors."""
from pathlib import Path
import datetime, shutil, hashlib, json, tarfile, os
P=Path(__file__).resolve().parent
S=P/'big6_periodic_t15_k2_20261121_0822'
name='big6v3_periodic_t15_k2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
R=P/name
R.mkdir(exist_ok=False)
items=('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json','machine.py','stub_native.py')
for n in items:shutil.copy2(S/n,R/n)
# Keep the domain8H sealed solver and the known-good T15 producer unchanged.
worker=(R/'worker_native.py').read_text()
assert "GROUPS=('t15',)" in worker and "order=(('t15','1'),('t15','2'))" in worker
assert 'seed_metrics(' not in worker
assert 'analyze(d,w,False)' in worker
manifest=json.loads((R/'t17b_manifest.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(R/'t17b_stage.tar.gz')==manifest['archive_sha256']
with tarfile.open(R/'t17b_stage.tar.gz') as tf:
 for member in tf.getmembers():
  if member.name.endswith('/src/setup.cpp'):
   data=tf.extractfile(member).read()
   assert hashlib.sha256(data).hexdigest()==manifest['variants']['periodic_t15_k2']['setup.cpp']
# Preserve scientific payload; Linux runtime gets its own verified copy.
plan=json.loads((R/'SESSION_PLAN.json').read_text())
assert plan['steps_per_T']==17950 and plan['single_session_cap_CU']==11.5
(R/'PATH_PAYLOAD_MAP.md').write_text('worker_native.py → PAYLOAD worker_native.py; native_analysis.py → PAYLOAD native_analysis.py; analyze_longspin.py → PAYLOAD analyze_longspin.py; assert_T17.py → PAYLOAD assert_T17.py; t17b_manifest.json → PAYLOAD t17b_manifest.json; t17b_stage.tar.gz → PAYLOAD t17b_stage.tar.gz; t17b_budget.json → controller generated PAYLOAD. remote_B.py → PAYLOAD remote_B.py. Extracted pack_stage/periodic_t15_k2/src and bin/FluidX3D originate in t17b_stage.tar.gz. Stub fixture alone provides stub_native.py.\n')
(R/'PAYLOAD_SHA256.json').write_text(json.dumps({n:sha(R/n) for n in items},indent=2)+'\n')
(R/'EXPERIMENT_CARD.md').write_text(f'''# T17 big-domain T15 k2 (fresh retry)\nHypothesis: Under frozen T17 v2 §3, two seeds yield admissible big-domain statistics; no group verdict in this task.\n唯一改动: controller reliability hardening relative to {S.name}; solver and physical payload unchanged.\n配置: {R}; archive SHA256 {sha(R/'t17b_stage.tar.gz')}; PAYLOAD_SHA256.json records each file.\n作业: Colab A100, ≤11.5 CU, root {R}; session pending.\n判据写定: T17 v2 §3, as frozen before this allocation; worker checks structure/finite/positive tau_x only. 25T + up to 3T V0 extensions + 2T statistics, two seeds; no science verdict until six groups.\n结论: pending.\n''')
print(R)
