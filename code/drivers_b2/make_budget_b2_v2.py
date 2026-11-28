#!/usr/bin/env python3
"""Version the B2 write-ahead correction; never overwrite the v1 science run."""
from pathlib import Path
import hashlib
here=Path(__file__).resolve().parent
src=here/'crc_input_package_v1'/'run_crc_inputs_b1.py'
out=here/'crc_input_package_v1'/'run_crc_inputs_b2_v2.py'
s=src.read_text()
start=s.index('def task_bytes(event):')
end=s.index('def save(path,obj):')
replacement='''def tree_bytes(path):
 return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink()) if path.exists() else 0

def cycle_bytes(event,cycle):
 return tree_bytes(ROOT/'raw'/cycle)+sum(tree_bytes(BASE/f'drivers_{event}_v1'/arm/cycle) for arm in ('AI','GFS'))+sum(p.stat().st_size for p in (ROOT/f'input_{cycle}_zero.nc',) if p.exists())

def batch_bytes():
 return tree_bytes(ROOT)+sum(tree_bytes(BASE/f'drivers_{event}_v1') for event in ('N8','N9','N10'))

def free_bytes():
 return shutil.disk_usage('/groups/kareem').free

def check(extra,stage,ledger):
 current=cycle_bytes(ledger['event'],ledger['cycle']);whole=batch_bytes();free=free_bytes()
 ledger['peak_bytes']=max(ledger['peak_bytes'],current)
 ledger['measurements'].append({'stage':stage,'cycle_bytes':current,'batch_bytes':whole,'next_bytes':extra,'free_bytes':free,'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
 # D-X storage clarification: earlier cycles count only toward batch cap.
 if current+extra>CAP or whole+extra>60_000_000_000 or free<650_000_000_000:
  raise RuntimeError(f'WRITE_AHEAD_STOP {stage}: cycle={current} batch={whole} next={extra} cycle_cap={CAP} batch_cap=60000000000 free={free} min_free=650000000000')

'''
assert 'def task_bytes(event):' in s and 'def save(path,obj):' in s
s=s[:start]+replacement+s[end:]
s=s.replace("work=ROOT/f'ops_{a.event}_{a.lead}_A_v1'","work=ROOT/f'ops_{a.event}_{a.lead}_A_v2'")
s=s.replace("ledger={'event':a.event,'phase':f'{a.event}_{a.lead}'", "ledger={'event':a.event,'cycle':dt.datetime.fromisoformat(gate.EVENTS[a.event]['leads'][a.lead]['t0']).strftime('%Y%m%d%H'),'phase':f'{a.event}_{a.lead}'")
# Distinct report basenames from v1 failed root; no overwrite of prior attempt.
s=s.replace("INPUT_GATE_{label}_v3.jsonl","INPUT_GATE_{label}_v4.jsonl").replace("INPUT_GATE_{label}_v3_SUMMARY.json","INPUT_GATE_{label}_v4_SUMMARY.json")
s=s.replace("DISK_LEDGER_{event}_{lead}_v1.json","DISK_LEDGER_{event}_{lead}_v2.json").replace("INPUT_NETCDF_MANIFEST_{a.event}_{a.lead}_v1.json","INPUT_NETCDF_MANIFEST_{a.event}_{a.lead}_v2.json").replace("INPUT_B1_{a.event}_{a.lead}_v1_SUMMARY.json","INPUT_B1_{a.event}_{a.lead}_v2_SUMMARY.json")
compile(s,str(out),'exec')
if out.exists():assert out.read_text()==s
else:out.write_text(s)
print(out,hashlib.sha256(out.read_bytes()).hexdigest())
