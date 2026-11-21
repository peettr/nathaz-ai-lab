#!/usr/bin/env python3
"""Freeze build11 transport and local Colab controller from build10 proven transport."""
from pathlib import Path
import tarfile,hashlib,json
R=Path(__file__).resolve().parent;B=R.parent/'build10_20261117_1356';SRC=R/'FluidX3D_facade_v10'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (R/'t9b11_source.tar.gz').exists()
with tarfile.open(R/'t9b11_source.tar.gz','w:gz') as t:t.add(SRC,arcname=SRC.name)
(R/'t9b11_manifest.json').write_text(json.dumps({'archive_sha256':sha(R/'t9b11_source.tar.gz'),'members':{p.relative_to(SRC).as_posix():sha(p) for p in SRC.rglob('*') if p.is_file()}},indent=2)+'\n')
for name in ('worker_gate.py','controller_gate.py','probe_gate.py','launch_gate.py'):
 s=(B/name).read_text()
 for old,new in [('t9b10','t9b11'),('t9b9_source','t9b11_source'),('t9b9_manifest','t9b11_manifest'),('FluidX3D_facade_v9','FluidX3D_facade_v10'),('luw-t9b10-g4-1117-a1','luw-t9b11-g4-1117-a1'),('build9 / researchos','build11 / researchos'),('T9b build10','T9b build11')]:s=s.replace(old,new)
 if name=='controller_gate.py':
  s=s.replace("'--max-hours','1'","'--max-hours','2'")
  s=s.replace("'--expect-hours','1'","'--expect-hours','2'")
  # The source package and manifest are both local; no v9 artefacts.
  assert "'t9b11_source.tar.gz','t9b11_manifest.json'" in s
 if name=='worker_gate.py':
  assert 'city_2000_difference.json' in s and 'stage_A_verdict.json' in s
 assert 't9b10' not in s and 't9b9' not in s and 'facade_v9' not in s
 (R/name).write_text(s)
print('archive',sha(R/'t9b11_source.tar.gz'),'files',len(json.loads((R/'t9b11_manifest.json').read_text())['members']))
