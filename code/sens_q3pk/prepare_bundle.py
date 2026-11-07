import csv,json,os,subprocess,hashlib,tarfile
from pathlib import Path
base=Path('./23_AI_Weather/06_Logs/ai_climate_emulator/site_stage_qc')
out=base/'sens_q3pk';out.mkdir(exist_ok=True)
rows=list(csv.DictReader((base/'final2/qc_log.csv').open()))
keys=sorted({(r['station'],r['season_year']) for r in rows if r['source']=='pk' and r['rules']=='Q3'})
files=['iem/%s_%s.gz'%k for k in keys]
# Include every archived ISD request (small), allowing Q5 to reuse prior responses.
files+=['isd/'+Path(json.loads(s)['file']).name for s in (base/'tacc_raw_receipts.jsonl').read_text().splitlines() if json.loads(s)['kind']=='isd']
files=sorted(set(files))
socket='./.ssh/sockets/[邮箱]'
cmd=['ssh','-n','-o','ControlPath='+socket,'-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]','tar -C /work2/04448/[用户]/超算/AI_Weather/site_stage_qc/raw -cf - '+ ' '.join(files)]
target=out/'source_stage.tar'
with target.open('xb') as f:
 p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE)
if p.returncode:raise RuntimeError(p.stderr.decode())
with tarfile.open(target) as t:
 names=t.getnames();assert len(names)==len(files) and set(names)==set(files)
print(json.dumps({'seasons':len(keys),'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
(out/'selected_keys.json').write_text(json.dumps(keys))
