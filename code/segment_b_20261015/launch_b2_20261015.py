import csv, hashlib, json, os, pathlib, subprocess, sys
p=pathlib.Path('/content')
rows=[json.loads(s) for s in (p/'r2_conus_main.jsonl').read_text().splitlines()]
keys=[(x['id'],x['lead_h'],x['source'],x.get('seed')) for x in rows if x['status']=='ok']
manifest=list(csv.DictReader((p/'segment_b_manifest.csv').open()))
assert len(rows)==230 and len(keys)==len(set(keys))==230
assert len(manifest)==18 and sum(x['group']=='conus' for x in manifest)==12
print('CHECKPOINT_OK',len(rows),hashlib.sha256((p/'r2_conus_main.jsonl').read_bytes()).hexdigest(),flush=True)
import torch
from earth2studio.models.px import StormCastCONUS
print('ENV_OK',torch.cuda.get_device_name(),flush=True)
log=(p/'segment_b2.log').open('a')
proc=subprocess.Popen([sys.executable,'-u','/content/continue_conus_b.py'],cwd='/content',stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(p/'r2_b2_pid').write_text(str(proc.pid))
print('LAUNCHED_PID',proc.pid,flush=True)
