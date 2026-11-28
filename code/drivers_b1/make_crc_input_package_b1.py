#!/usr/bin/env python3
"""Create fresh, event-scoped CRC A-stage package from audited R1/R2 implementation."""
from pathlib import Path
import json, hashlib, re, shutil
HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]/'k_gc37_prereg'/'r1r2_v1'
CONFIG=HERE.parent/'event_times_bbox_gc37x.json'
OUT=HERE/'crc_input_package_v1'
REMOTE='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
EVENTS=json.loads(CONFIG.read_text())['events']
assert set(('N1','N3','N4')).issubset(EVENTS)

def emit(name, text):
    path=OUT/name
    if path.exists():
        assert path.read_text()==text, f'existing differs: {path}'
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    return path

def change(src, pairs):
    t=(SRC/src).read_text()
    for old,new in pairs:
        assert old in t, (src,old)
        t=t.replace(old,new)
    return t

# Complete source-file imports are staged together; keep source originals untouched.
for name in ('apcp_identical_v2.py','download_checked_r1r2_v2.py'):
    found=list(HERE.parents[1].glob(name)) + list(SRC.glob(name))
    if not found:
        raise FileNotFoundError(name)
    emit(name,found[0].read_text())
prep=change('prepare_gc37_gfs_2024_r1r2_v3.py',[
    ('from download_checked_r1r2_v2 import get as verified_get','from download_checked_r1r2_v2 import get as verified_get'),
    ("BASE='https://osdf-director.osg-htc.org/ncar/gdex/'", "BASE='https://osdf-director.osg-htc.org/ncar/gdex/'"),
    ("/2024/{t:%Y%m%d}/", "/{t:%Y}/{t:%Y%m%d}/"),
])
emit('prepare_gc37_b1.py',prep)
gate=change('numeric_gate_r1r2_v3.py',[
    ('from prepare_gc37_gfs_2024_r1r2_v1 import download, url','from prepare_gc37_b1 import url'),
    ("ROOT=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_R1R2_v1')",f"ROOT=pathlib.Path('{REMOTE}/inputs_N1N3N4_v1')"),
    ("EVENTS=json.loads((pathlib.Path(__file__).resolve().parent/'event_times_gc37.json').read_text())", "EVENTS=json.loads((pathlib.Path(__file__).resolve().parent/'event_times_bbox_gc37x.json').read_text())['events']"),
    ("CROP={'R1':(slice(148,265),slice(960,1153)), 'R2':(slice(144,261),slice(952,1145))}  # north-to-south lat / 0..360 lon", "CROP={e:(slice(int(round((90-v['domain']['crop_lat'][1])*4)),int(round((90-v['domain']['crop_lat'][0])*4))+1),slice(int(round((360+v['domain']['crop_lon_west_neg'][0])*4)),int(round((360+v['domain']['crop_lon_west_neg'][1])*4))+1)) for e,v in EVENTS.items() if e in ('N1','N3','N4')}"),
    ("for event in ('R1','R2'):", "for event in ('N1','N3','N4'):"),
])
# For A-stage f006, fields are precipitation only unless the file is also a boundary forecast.
# Existing inspected boundary full-field path is retained and can stop on any missing required field.
emit('numeric_gate_b1.py',gate)
run=change('run_crc_inputs_r1r2_v3.py',[
    ('import numeric_gate_r1r2_v3 as gate','import numeric_gate_b1 as gate'),
    ("BASE=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')",f"BASE=Path('{REMOTE}')"),
    ("ROOT=BASE/'inputs_2024_R1R2_v1'", "ROOT=BASE/'inputs_N1N3N4_v1'"),
    ("CYCLES=[('R2','24h'),('R1','24h'),('R1','48h'),('R1','72h'),('R2','48h'),('R2','72h')]", "CYCLES=[(e,l) for e in ('N1','N3','N4') for l in ('24h','48h','72h')]"),
    ("ap.add_argument('--phase',choices=('trial','rest'),required=True);a=ap.parse_args()", "ap.add_argument('--event',choices=('N1','N3','N4'),required=True);ap.add_argument('--lead',choices=('24h','48h','72h'),required=True);a=ap.parse_args()"),
    ("work=ROOT/('ops_r2_24_v3' if a.phase=='trial' else 'ops_rest_v3')", "work=ROOT/f'ops_{a.event}_{a.lead}_A_v1'"),
    ("os.environ.get('GC37_PHASE')==a.phase", "os.environ.get('GC37_EVENT')==a.event"),
    ("if a.phase=='rest':validate_pilot_nc()", "# Each event-cycle is independent; a previous cycle is not a dependency."),
    ("gate.EVENTS=json.loads((HERE/'event_times_gc37.json').read_text())", "gate.EVENTS=json.loads((HERE/'event_times_bbox_gc37x.json').read_text())['events']"),
    ("assert len(objects)==90", "assert len(objects)==135"),
    ("for event in ('R1','R2')", "for event in ('N1','N3','N4')"),
    ("chosen=CYCLES[:1] if a.phase=='trial' else CYCLES[1:]", "chosen=[(a.event,a.lead)]"),
    ("'phase':a.phase", "'phase':f'{a.event}_{a.lead}'"),
    ("resume=(a.phase=='rest' and cycle=='2024073100')", "resume=False"),
    ("if raw.exists() and not resume:raise FileExistsError(raw)", "if raw.exists():raise FileExistsError(raw)"),
    ("if resume and not raw.is_dir():raise FileNotFoundError(raw)", ""),
    ("if resume:\n   old=ROOT/f'INPUT_GATE_{label}_v2.jsonl'\n   if not old.is_file():raise FileNotFoundError(old)\n   prior={r['key']:r['sha256'] for r in map(json.loads,old.read_text().splitlines()) if r['ok']}", ""),
    ("if not resume:raw.mkdir()", "raw.mkdir()"),
    ("if resume and not meta['reused']:raise RuntimeError(('resume_expected_existing_file',target))", ""),
    ("str(HERE/'prepare_gc37_gfs_2024_r1r2_v3.py')", "str(HERE/'prepare_gc37_b1.py')"),
])
# B stage is separately scheduled only after the A-stage success; preserve raw until B has read it.
start=run.index("  ops=BASE/f'drivers_gc37_{event}_v1'")
end=run.index("  print('CYCLE_READY'",start)
run=run[:start]+"  ledger['cycles'].append({'cycle':cycle,'event':event,'lead':lead,'verified_files':len(rows),'netcdf_sha256':digest(nc),'raw_retained_for_B':True})\n  (ROOT/f'DISK_LEDGER_{event}_{lead}_v1.json').write_text(json.dumps(ledger,indent=2))\n"+run[end:]
run=run.replace("f'INPUT_NETCDF_MANIFEST_{a.phase}_v3.json'", "f'INPUT_NETCDF_MANIFEST_{a.event}_{a.lead}_v1.json'")
run=run.replace("f'INPUT_R1R2_{a.phase}_v3_SUMMARY.json'", "f'INPUT_B1_{a.event}_{a.lead}_v1_SUMMARY.json'")
run=run.replace("f'DISK_LEDGER_{a.phase}_v3.json'", "f'DISK_LEDGER_{a.event}_{a.lead}_v1.json'")
run=run.replace("print('PHASE_READY',a.phase,len(chosen),flush=True)","print('PHASE_READY',a.event,a.lead,len(chosen),flush=True)")
# quota RPC is known unreliable; only filesystem free-space is the approved gate.
old=""" text=subprocess.check_output(['quota','/groups/kareem'],text=True,timeout=40)
 row=[x for x in text.splitlines() if x.startswith('/groups/kareem')]
 if len(row)!=1:raise RuntimeError(('quota_parse',text))
 m=re.search(r'(\\d+(?:\\.\\d+)?)([KMGTP])\\s*$',row[0])
 if not m:raise RuntimeError(('quota_avail_parse',text))
 return min(fs,int(float(m.group(1))*1024**('KMGTP'.index(m.group(2))+1)))"""
assert old in run
run=run.replace(old," return fs")
# three cycles per event collectively must stay under the event cap, counting retained inputs and final WPS.
run=run.replace("roots=(ROOT,BASE/'drivers_gc37_R1_v1',BASE/'drivers_gc37_R2_v1')", "roots=(ROOT,BASE/'drivers_N1_v1',BASE/'drivers_N3_v1',BASE/'drivers_N4_v1')")
# Event-specific capacity is checked in job wrapper; netcdf and GRIB remain until B stage.
emit('run_crc_inputs_b1.py',run)
emit('event_times_bbox_gc37x.json',CONFIG.read_text())
# Source provenance and generated syntax gates.
for p in OUT.glob('*.py'):
    compile(p.read_text(),str(p),'exec')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file()}
emit('PACKAGE_SHA256.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'files':manifest,'cycles':[(e,l) for e in ('N1','N3','N4') for l in ('24h','48h','72h')]},indent=2))
