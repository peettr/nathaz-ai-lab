from pathlib import Path
import json,hashlib,tarfile
r=Path(__file__).resolve().parent;s=r/'stage_fixed';m=s/'stage_manifest.json'
obj=json.loads(m.read_text());obj['setup_sha256']=hashlib.sha256((s/'FluidX3D/src/setup.cpp').read_bytes()).hexdigest();m.write_text(json.dumps(obj,indent=2)+'\n')
a=r/'stage_fixed_bundle.tar.gz'
with tarfile.open(a,'x:gz') as tf:
 for p in sorted(s.rglob('*')):
  if p.is_file():tf.add(p,arcname=p.relative_to(s))
print('FIXED_SETUP_SHA256',obj['setup_sha256'],'FIXED_ARCHIVE_SHA256',hashlib.sha256(a.read_bytes()).hexdigest())
