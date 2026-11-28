#!/usr/bin/env python3
"""Delete only six verified initialization GRIB per paired B2 cycle."""
import pathlib,json,hashlib,sys,datetime as dt,subprocess
root=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
iroot=root/'inputs_N8N9N10_v1'
assert sys.argv[1] in ('--check','--execute')
action=sys.argv[1];ledger=iroot/'PAIR_READBACK_GRIB_CLEANUP_5_20261125_v1.json'
assert not ledger.exists(),'ledger already exists; no repeat'
config=json.loads((iroot/'event_times_bbox_gc37x.json').read_text())['events']
plans=[]
for event,lead in [('N8','24h'),('N8','48h'),('N9','24h'),('N9','48h'),('N10','24h')]:
    spec=config[event]['leads'][lead];cycle=dt.datetime.fromisoformat(spec['t0']).strftime('%Y%m%d%H')
    driver=root/f'drivers_{event}_v1'
    n=int(spec['length_h']//6)+1
    ai=sorted((driver/'AI'/cycle).glob('FILE:*'));gfs=sorted((driver/'GFS'/cycle).glob('FILE:*'))
    assert len(ai)==len(gfs)==n and [p.name for p in ai]==[p.name for p in gfs]
    # Independent full paired numerical/geometry audit must be separately archived before execute.
    gate=iroot/f'INPUT_GATE_{event}_{lead}_{cycle}_v3_SUMMARY.json'
    summary=json.loads(gate.read_text());assert summary['all_pass'] and summary['global_input_checked']
    source={json.loads(line)['url'].split('/')[-1]:json.loads(line)['sha256'] for line in pathlib.Path(summary['jsonl']).read_text().splitlines()}
    t0=dt.datetime.strptime(cycle,'%Y%m%d%H');tm6=(t0-dt.timedelta(hours=6)).strftime('%Y%m%d%H');tm12=(t0-dt.timedelta(hours=12)).strftime('%Y%m%d%H')
    names={f'gfs.0p25.{tm12}.f006.grib2',f'gfs.0p25.{tm6}.f000.grib2',f'gfs.0p25.{tm6}.f006.grib2',f'gfs.0p25.{cycle}.f000.grib2',f'gfs.0p25b.{tm6}.f000.grib2',f'gfs.0p25b.{cycle}.f000.grib2'}
    d=iroot/'raw'/cycle;actual={p.name for p in d.glob('*.grib2')};assert actual==names,(d,actual,names)
    assert all(n in source for n in names)
    assert (iroot/f'input_{cycle}_zero.nc').is_file()
    for name in sorted(names):
        p=d/name;assert p.is_file() and not p.is_symlink()
        plans.append({'event':event,'cycle':cycle,'path':str(p),'bytes':p.stat().st_size,'sha256_expected':source[name]})
assert len(plans)==30
if action=='--check':
    print(json.dumps({'mode':'check','files':len(plans),'bytes':sum(p['bytes'] for p in plans),'cycles':sorted(set(p['cycle'] for p in plans))}));sys.exit()
before=subprocess.check_output(['df','-B1','/groups/kareem'],text=True)
for obj in plans:
    p=pathlib.Path(obj['path']);h=hashlib.sha256()
    with p.open('rb') as f:
        for buf in iter(lambda:f.read(8*1024*1024),b''):h.update(buf)
    assert h.hexdigest()==obj['sha256_expected'],obj['path']
for obj in plans:
    p=pathlib.Path(obj['path']);assert p.stat().st_size==obj['bytes']
    p.unlink();assert not p.exists()
after=subprocess.check_output(['df','-B1','/groups/kareem'],text=True)
record={'files_deleted':len(plans),'bytes_deleted':sum(p['bytes'] for p in plans),'files':plans,'df_before':before,'df_after':after,'input_netcdf_retained':True,'graphcast_raw_retained':True}
assert not ledger.exists();ledger.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'mode':'executed','ledger':str(ledger),'files_deleted':len(plans),'bytes_deleted':record['bytes_deleted'],'df_before':before,'df_after':after}))
