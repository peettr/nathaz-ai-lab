#!/usr/bin/env python3
"""Delete only the 6 retained analysis t0/t-6h GRIBs per paired cycle."""
import pathlib,json,hashlib,sys,os,datetime as dt,subprocess
root=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
iroot=root/'inputs_N1N3N4_v1'
assert sys.argv[1] in ('--check','--execute')
action=sys.argv[1]; ledger=iroot/'PAIR_READBACK_GRIB_CLEANUP_20261124_v1.json'
assert not ledger.exists(),'ledger already exists; no repeat'
config=json.loads((iroot/'event_times_bbox_gc37x.json').read_text())['events']
plans=[]
for event in ('N1','N3','N4'):
    driver=root/f'drivers_{event}_v1'; report=json.loads((driver/f'READBACK_GC37X_{event}_V1.json').read_text())
    assert len(report['cycles'])==3 and report['files']==60
    for cycle,item in report['cycles'].items():
        assert item['five_fields_31_levels_finite'] and item['shared_byte_equal_pairs']==item['pairs'] and item['t0_identical']
        assert item['pairs'] in (6,10,14) and report['d01_coverage']['minimum_margin_deg']>=3
        assert all(p['shared_surface_byte_equal'] for p in item['pairs_detail'])
        assert len(item['pairs_detail'])==item['pairs']
        gate=sorted(iroot.glob(f'INPUT_GATE_{event}_*_{cycle}_v*_SUMMARY.json'))
        assert gate
        summary=json.loads(gate[-1].read_text());assert summary['all_pass'] and summary['global_input_checked']
        source={json.loads(line)['url'].split('/')[-1]:json.loads(line)['sha256'] for line in pathlib.Path(summary['jsonl']).read_text().splitlines()}
        t0=dt.datetime.strptime(cycle,'%Y%m%d%H');tm6=(t0-dt.timedelta(hours=6)).strftime('%Y%m%d%H');tm12=(t0-dt.timedelta(hours=12)).strftime('%Y%m%d%H')
        names={f'gfs.0p25.{tm12}.f006.grib2',f'gfs.0p25.{tm6}.f000.grib2',f'gfs.0p25.{tm6}.f006.grib2',f'gfs.0p25.{cycle}.f000.grib2',f'gfs.0p25b.{tm6}.f000.grib2',f'gfs.0p25b.{cycle}.f000.grib2'}
        d=iroot/'raw'/cycle;actual={p.name for p in d.glob('*.grib2')};assert actual==names,(d,actual,names)
        assert all(n in source for n in names)
        for name in sorted(names):
            p=d/name;assert p.is_file() and not p.is_symlink()
            plans.append({'event':event,'cycle':cycle,'path':str(p),'bytes':p.stat().st_size,'sha256_expected':source[name]})
assert len(plans)==54
if action=='--check':
    print(json.dumps({'mode':'check','files':len(plans),'bytes':sum(p['bytes'] for p in plans),'cycles':sorted(set(p['cycle'] for p in plans))}));sys.exit()
before=subprocess.check_output(['df','-B1','/groups/kareem'],text=True)
for obj in plans:
    p=pathlib.Path(obj['path']);h=hashlib.sha256()
    with p.open('rb') as f:
        for buf in iter(lambda:f.read(8*1024*1024),b''):h.update(buf)
    assert h.hexdigest()==obj['sha256_expected'],obj['path']
# Full preverification before first deletion: do not partially remove on SHA failure.
for obj in plans:
    p=pathlib.Path(obj['path']);assert p.stat().st_size==obj['bytes']
    p.unlink();assert not p.exists()
after=subprocess.check_output(['df','-B1','/groups/kareem'],text=True)
record={'files_deleted':len(plans),'bytes_deleted':sum(p['bytes'] for p in plans),'files':plans,'df_before':before,'df_after':after,'input_netcdf_retained':True,'graphcast_raw_retained':True}
assert not ledger.exists();ledger.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'mode':'executed','ledger':str(ledger),'files_deleted':len(plans),'bytes_deleted':record['bytes_deleted'],'df_before':before,'df_after':after}))
