"""Stage only 36 archived IEM seasons and existing ISD records; no re-download."""
import csv,json,subprocess,hashlib,tarfile
from pathlib import Path
base=Path(__file__).resolve().parents[1]
out=Path(__file__).resolve().parent
rows=list(csv.DictReader((base/'final2/qc_log.csv').open()))
keys=sorted({(r['station'],r['season_year']) for r in rows if r['rules']=='Q3'})
assert len(keys)==36,(len(keys),keys)
files=['iem/%s_%s.gz'%k for k in keys]
files+=['isd/'+Path(json.loads(s)['file']).name for s in (base/'tacc_raw_receipts.jsonl').read_text().splitlines() if json.loads(s)['kind']=='isd']
files=sorted(set(files))
socket='./.ssh/sockets/[邮箱]'
cmd=['ssh','-n','-o','ControlPath='+socket,'-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]','tar -C /work2/04448/[用户]/超算/AI_Weather/site_stage_qc/raw -cf - '+' '.join(files)]
target=out/'source_stage.tar'
with target.open('xb') as f:
 p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE)
if p.returncode:raise RuntimeError(p.stderr.decode())
with tarfile.open(target) as t:
 names=t.getnames();assert len(names)==len(files) and set(names)==set(files)
(out/'selected_keys.json').write_text(json.dumps(keys))
print(json.dumps({'seasons':len(keys),'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
