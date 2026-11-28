#!/usr/bin/env python3
"""Version AI WPS consumer for actual B2 raw layout; preserve v1."""
from pathlib import Path
import hashlib, json
here=Path(__file__).resolve().parent
src=here/'wps_package_v1';out=here/'wps_ai_package_v2';out.mkdir(exist_ok=True)
s=(src/'build_gc37x_wps_ai_b2.py').read_text()
old="f=RAW/a.cycle/f'step_{step:02d}.npz'";new="f=RAW/'raw'/EVENT/a.cycle/f'step_{step:02d}.npz'"
assert s.count(old)==1
s=s.replace(old,new)
p=out/'build_gc37x_wps_ai_b2v2.py'
if p.exists():assert p.read_text()==s
else:p.write_text(s)
base='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
for e in ('N8','N9','N10'):
 for lead in ('24h','48h','72h'):
  s=(src/f'submit_{e}_{lead}_AI_b2.sh').read_text()
  s=s.replace(f'ops_{e}_{lead}_AI_b2',f'ops_{e}_{lead}_AI_b2v2')
  s=s.replace('build_gc37x_wps_ai_b2.py','build_gc37x_wps_ai_b2v2.py')
  p=out/f'submit_{e}_{lead}_AI_b2v2.sh'
  if p.exists():assert p.read_text()==s
  else:p.write_text(s)
for n in ('wps_format5.py','COMMON_LEVELS.txt','event_times_bbox_gc37x.json'):
 if n in ('COMMON_LEVELS.txt',): continue
 source=(src/n) if (src/n).exists() else (here.parent/n)
 text=source.read_text();p=out/n
 if p.exists():assert p.read_text()==text
 else:p.write_text(text)
for p in out.glob('*.py'):compile(p.read_text(),str(p),'exec')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='SHA256.json'}
p=out/'SHA256.json';text=json.dumps(manifest,indent=2)+'\n'
if p.exists():assert p.read_text()==text
else:p.write_text(text)
print(out)
