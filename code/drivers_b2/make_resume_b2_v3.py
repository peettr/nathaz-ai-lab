#!/usr/bin/env python3
"""Version the approved 550 GB in-job gate and immutable verified-file resume."""
from pathlib import Path
import hashlib
here=Path(__file__).resolve().parent
src=here/'crc_input_package_v1'/'run_crc_inputs_b2_v2.py'
out=here/'crc_input_package_v1'/'run_crc_inputs_b2_v3.py'
s=src.read_text()
s=s.replace('free<650_000_000_000','free<550_000_000_000').replace('min_free=650000000000','min_free=550000000000')
s=s.replace("work=ROOT/f'ops_{a.event}_{a.lead}_A_v2'","work=ROOT/f'ops_{a.event}_{a.lead}_A_v3'")
s=s.replace("  resume=False\n  if raw.exists():raise FileExistsError(raw)\n  \n  prior={}\n",'''  prior_path=ROOT/f'INPUT_GATE_{label}_v4.jsonl'
  if not raw.is_dir() or not prior_path.is_file():raise FileNotFoundError(('resume_inputs',raw,prior_path))
  prior={r['key']:r for line in prior_path.read_text().splitlines() if (r:=json.loads(line)).get('ok')}
''')
s=s.replace("  raw.mkdir()\n  report=ROOT/f'INPUT_GATE_{label}_v4.jsonl';rows=[]",'''  if (ROOT/f'input_{cycle}_zero.nc').exists():raise FileExistsError(ROOT/f'input_{cycle}_zero.nc')
  report=ROOT/f'INPUT_GATE_{label}_v5.jsonl';rows=[]''')
s=s.replace("     meta=get(url,target,before_write=callback,prior_sha=prior.get(gate.str_key(key)))",'''     previous=prior.get(gate.str_key(key))
     if target.exists() and previous is None:raise RuntimeError(('unproven_existing_file',target))
     meta=get(url,target,before_write=callback,prior_sha=previous['sha256'] if previous else None)
     if meta['reused'] and (not previous or meta['bytes']!=previous['bytes']):raise RuntimeError(('resume_provenance_mismatch',target))''')
s=s.replace('INPUT_GATE_{label}_v4_SUMMARY.json','INPUT_GATE_{label}_v5_SUMMARY.json')
s=s.replace('DISK_LEDGER_{event}_{lead}_v2.json','DISK_LEDGER_{event}_{lead}_v3.json')
s=s.replace('INPUT_NETCDF_MANIFEST_{a.event}_{a.lead}_v2.json','INPUT_NETCDF_MANIFEST_{a.event}_{a.lead}_v3.json')
s=s.replace('INPUT_B1_{a.event}_{a.lead}_v2_SUMMARY.json','INPUT_B1_{a.event}_{a.lead}_v3_SUMMARY.json')
s=s.replace("ROOT/f'DISK_LEDGER_{a.event}_{a.lead}_v1.json'","ROOT/f'DISK_LEDGER_{a.event}_{a.lead}_v3.json'")
# Admission is based on only missing source objects, not previously verified files.
s=s.replace('estimate=math.ceil(sum(lengths.values())*1.1)+math.ceil(NC_REF*1.2)+math.ceil(n_wps*WPS_REF*1.2)', '''missing=[(k,u) for k,u in selected if not (raw/u.rsplit('/',1)[-1]).exists()]
  estimate=math.ceil(sum(lengths[gate.str_key(k)] for k,u in missing)*1.1)+math.ceil(NC_REF*1.2)+math.ceil(n_wps*WPS_REF*1.2)
  print('RESUME_BUDGET',label,'verified_existing',len(selected)-len(missing),'missing',len(missing),'next_bytes',estimate,flush=True)''')
assert s!=src.read_text()
compile(s,str(out),'exec')
if out.exists():assert out.read_text()==s
else:out.write_text(s)
print(str(out),hashlib.sha256(out.read_bytes()).hexdigest())
