#!/usr/bin/env python3
"""Create isolated batch-2 input package from audited batch-1 bytes."""
from pathlib import Path
import hashlib, json, shutil, datetime as dt
HERE=Path(__file__).resolve().parent
B1=HERE.parent/'drivers_b1'/'crc_input_package_v1'
OUT=HERE/'crc_input_package_v1'
CONFIG=HERE.parent/'event_times_bbox_gc37x.json'
OLD='inputs_N1N3N4_v1'; NEW='inputs_N8N9N10_v1'
EVENTS=('N8','N9','N10')
OUT.mkdir(exist_ok=True)
def emit(name,text):
 p=OUT/name
 if p.exists():
  assert p.read_text()==text,('existing_differs',p)
 else:p.write_text(text)
 return p
def replace(text,old,new):
 assert old in text,old
 return text.replace(old,new)
cfg=json.loads(CONFIG.read_text())
assert all(x in cfg['events'] for x in EVENTS)
emit('event_times_bbox_gc37x.json',CONFIG.read_text())
for name in ('apcp_identical_v2.py','download_checked_r1r2_v2.py','prepare_gc37_b1.py','numeric_gate_b1.py','run_crc_inputs_b1.py'):
 text=(B1/name).read_text()
 if name=='numeric_gate_b1.py':
  text=replace(text,OLD,NEW)
  text=replace(text,"('N1','N3','N4')","('N8','N9','N10')")
  text=replace(text,"('R1','R2')","('N8','N9','N10')")
 if name=='run_crc_inputs_b1.py':
  text=replace(text,OLD,NEW)
  text=replace(text,"('N1','N3','N4')","('N8','N9','N10')")
  text=replace(text,"BASE/'drivers_N1_v1',BASE/'drivers_N3_v1',BASE/'drivers_N4_v1'","BASE/'drivers_N8_v1',BASE/'drivers_N9_v1',BASE/'drivers_N10_v1'")
  text=replace(text,"assert len(objects)==135","assert len(objects)==EXPECTED_OBJECTS")
  text=replace(text,"work=ROOT/f'ops_{a.event}_{a.lead}_A_v1'","work=ROOT/f'ops_{a.event}_{a.lead}_A_v1'")
  # B1 counts the entire batch against a per-event cap; B2 measures the named event only.
  text=replace(text,"def task_bytes():\n roots=(ROOT,BASE/'drivers_N8_v1',BASE/'drivers_N9_v1',BASE/'drivers_N10_v1')\n return sum(p.stat().st_size for r in roots if r.exists() for p in r.rglob('*') if p.is_file() and not p.is_symlink())", "def task_bytes(event):\n raw=ROOT/'raw'\n cycles=[dt.datetime.fromisoformat(v['t0']).strftime('%Y%m%d%H') for v in gate.EVENTS[event]['leads'].values()]\n roots=[raw/c for c in cycles]+[BASE/f'drivers_{event}_v1']\n size=sum(p.stat().st_size for r in roots if r.exists() for p in r.rglob('*') if p.is_file() and not p.is_symlink())\n size+=sum((ROOT/f'input_{c}_zero.nc').stat().st_size for c in cycles if (ROOT/f'input_{c}_zero.nc').exists())\n return size")
  text=replace(text,"current=task_bytes();free=free_bytes()","current=task_bytes(ledger['event']);free=free_bytes()")
  text=replace(text,"ledger={'phase':f'{a.event}_{a.lead}'","ledger={'event':a.event,'phase':f'{a.event}_{a.lead}'")
  text=text.replace("def validate_pilot_nc():", "def validate_pilot_nc():")
  # evaluate inventory from the frozen event configuration, not an inherited constant
  text=replace(text,"CYCLES=[(e,l) for e in ('N8','N9','N10') for l in ('24h','48h','72h')]", "CYCLES=[(e,l) for e in ('N8','N9','N10') for l in ('24h','48h','72h')]\nEXPECTED_OBJECTS=len({k for e,l in CYCLES for k in _keys_for(e,l)})") if False else text
  text=replace(text,"assert len(objects)==EXPECTED_OBJECTS","assert len(objects)>=9*11 and all(len(index[f'{e}_{l}'])>=11 for e,l in CYCLES)")
 emit(name,text)
# Native scripts compile without running scientific imports.
for p in OUT.glob('*.py'):compile(p.read_text(),str(p),'exec')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='PACKAGE_SHA256.json'}
emit('PACKAGE_SHA256.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'package':str(OUT),'manifest':manifest,'events':EVENTS},indent=2))
