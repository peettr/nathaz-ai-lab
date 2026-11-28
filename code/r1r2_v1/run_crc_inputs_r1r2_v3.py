#!/usr/bin/env python3
"""CRC serial input gate; trial R2-24 then five in distinct scheduler root."""
import argparse, datetime as dt, json, math, os, re, shutil, subprocess, sys
import numpy as np
import xarray as xr
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import numeric_gate_r1r2_v3 as gate
from download_checked_r1r2_v2 import get,digest,expected_bytes
BASE=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
ROOT=BASE/'inputs_2024_R1R2_v1'
CAP=20_000_000_000; MIN_FREE=100_000_000_000
NC_REF=1_051_706_791; WPS_REF=15_575_632 # measured E2/E3 largest on CRC
CYCLES=[('R2','24h'),('R1','24h'),('R1','48h'),('R1','72h'),('R2','48h'),('R2','72h')]

def task_bytes():
 roots=(ROOT,BASE/'drivers_gc37_R1_v1',BASE/'drivers_gc37_R2_v1')
 return sum(p.stat().st_size for r in roots if r.exists() for p in r.rglob('*') if p.is_file() and not p.is_symlink())

def free_bytes():
 fs=shutil.disk_usage('/groups/kareem').free
 text=subprocess.check_output(['quota','/groups/kareem'],text=True,timeout=40)
 row=[x for x in text.splitlines() if x.startswith('/groups/kareem')]
 if len(row)!=1:raise RuntimeError(('quota_parse',text))
 m=re.search(r'(\d+(?:\.\d+)?)([KMGTP])\s*$',row[0])
 if not m:raise RuntimeError(('quota_avail_parse',text))
 return min(fs,int(float(m.group(1))*1024**('KMGTP'.index(m.group(2))+1)))

def check(extra,stage,ledger):
 current=task_bytes();free=free_bytes()
 ledger['peak_bytes']=max(ledger['peak_bytes'],current)
 ledger['measurements'].append({'stage':stage,'task_bytes':current,'next_bytes':extra,'free_bytes':free,'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
 if current+extra>=CAP or free-extra<=MIN_FREE:
  raise RuntimeError(f'WRITE_AHEAD_STOP {stage}: task={current} next={extra} cap={CAP} free={free} reserve={MIN_FREE}')

def save(path,obj):
 with path.open('x') as f:json.dump(obj,f,indent=2)

def run(argv,env=None):
 print('RUN',argv,flush=True);subprocess.run(argv,check=True,env=env)

def validate_pilot_nc():
 path=ROOT/'input_2024060318_zero.nc'
 if not path.is_file():raise FileNotFoundError(path)
 report={'netcdf':str(path),'variables':{},'all_finite':True}
 with xr.open_dataset(path,engine='netcdf4') as ds:
  for name in ds.data_vars:
   v=ds[name]
   # NetCDF reads are sliced by time/level to avoid allocating a full 37-layer stack.
   n=0
   if 'level' in v.dims:
    for t in range(v.sizes['time']):
     for p in range(v.sizes['level']):n+=int(np.count_nonzero(~np.isfinite(v.isel(time=t,level=p).values)))
   elif 'time' in v.dims:
    for t in range(v.sizes['time']):n+=int(np.count_nonzero(~np.isfinite(v.isel(time=t).values)))
   else:n=int(np.count_nonzero(~np.isfinite(v.values)))
   report['variables'][name]=n
   if n:report['all_finite']=False
 save(ROOT/'R2_24_GLOBAL_INPUT_RECHECK_V3.json',report)
 if not report['all_finite']:raise RuntimeError(('pilot_global_nonfinite',report))
 print('PILOT_GLOBAL_FINITE',str(path),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=('trial','rest'),required=True);a=ap.parse_args()
 work=ROOT/('ops_r2_24_v3' if a.phase=='trial' else 'ops_rest_v3')
 assert Path.cwd().resolve()==work and os.environ.get('GC37_PHASE')==a.phase
 assert ROOT.is_dir() and (ROOT/'raw').is_dir()
 if a.phase=='rest':validate_pilot_nc()
 gate.ROOT=ROOT;gate.EVENTS=json.loads((HERE/'event_times_gc37.json').read_text())
 objects,index=gate.expected();assert len(objects)==90
 gate.precip_times={k[1] for k in objects if k[0]=='d084001' and k[2]==6}
 refs={gate.str_key(k):{event for event in ('R1','R2') if any(gate.str_key(k) in keys for name,keys in index.items() if name.startswith(event+'_'))} for k in objects}
 chosen=CYCLES[:1] if a.phase=='trial' else CYCLES[1:]
 ledger={'phase':a.phase,'cap_bytes':CAP,'peak_bytes':0,'measurements':[],'cycles':[],'nc_reference_bytes':NC_REF,'wps_reference_bytes':WPS_REF}
 manifest=[]
 for event,lead in chosen:
  spec=gate.EVENTS[event]['leads'][lead];cycle=dt.datetime.fromisoformat(spec['t0']).strftime('%Y%m%d%H')
  label=f'{event}_{lead}_{cycle}';raw=ROOT/'raw'/cycle
  resume=(a.phase=='rest' and cycle=='2024073100')
  if raw.exists() and not resume:raise FileExistsError(raw)
  if resume and not raw.is_dir():raise FileNotFoundError(raw)
  prior={}
  if resume:
   old=ROOT/f'INPUT_GATE_{label}_v2.jsonl'
   if not old.is_file():raise FileNotFoundError(old)
   prior={r['key']:r['sha256'] for r in map(json.loads,old.read_text().splitlines()) if r['ok']}
  keys=set(index[f'{event}_{lead}']);selected=[(k,u) for k,u in objects.items() if gate.str_key(k) in keys]
  lengths={gate.str_key(k):expected_bytes(u)[0] for k,u in selected}
  n_wps=1+int(spec['length_h'])//6
  estimate=math.ceil(sum(lengths.values())*1.1)+math.ceil(NC_REF*1.2)+math.ceil(n_wps*WPS_REF*1.2)
  check(estimate,label+':cycle_start',ledger)
  if not resume:raw.mkdir()
  report=ROOT/f'INPUT_GATE_{label}_v3.jsonl';rows=[]
  with report.open('x') as stream:
   for i,(key,url) in enumerate(selected,1):
    target=raw/url.rsplit('/',1)[-1]
    try:
     callback=lambda size,stage:check(size,label+':'+stage,ledger)
     meta=get(url,target,before_write=callback,prior_sha=prior.get(gate.str_key(key)))
     if resume and not meta['reused']:raise RuntimeError(('resume_expected_existing_file',target))
     if meta['bytes']!=lengths[gate.str_key(key)]:raise RuntimeError(('length_changed',url))
     rec=gate.inspect(key,target,refs[gate.str_key(key)]);rec['download']=meta
    except Exception as exc:rec={'key':gate.str_key(key),'url':url,'ok':False,'errors':[f'{type(exc).__name__}: {exc}']}
    rows.append(rec);stream.write(json.dumps(rec)+'\n');stream.flush()
    print('GATE_FILE',label,i,len(selected),rec['key'],'OK' if rec['ok'] else 'FAIL',flush=True)
    if not rec['ok']:raise RuntimeError(('INPUT_GATE_FAILED',label,rec))
  assert len(rows)==len(selected) and all(r['ok'] for r in rows)
  save(ROOT/f'INPUT_GATE_{label}_v3_SUMMARY.json',{'cycle':cycle,'event':event,'lead':lead,'files':len(rows),'all_pass':True,'dedup_identical':sum(r.get('apcp_dedup',{}).get('dedup_identical',0) for r in rows),'jsonl':str(report),'source_lengths':lengths,'global_input_checked':True})
  check(math.ceil(NC_REF*1.2),label+':before_netcdf',ledger)
  run([sys.executable,str(HERE/'prepare_gc37_gfs_2024_r1r2_v3.py'),'--cycle',cycle,'--root',str(ROOT),'--raw-dir',str(raw)])
  nc=ROOT/f'input_{cycle}_zero.nc';prov=ROOT/f'input_{cycle}_zero.json'
  assert nc.is_file() and prov.is_file() and json.loads(prov.read_text())['input_sha256']==digest(nc)
  manifest.append({'event':event,'lead':lead,'cycle':cycle,'netcdf':nc.name,'sha256':digest(nc),'bytes':nc.stat().st_size})
  ops=BASE/f'drivers_gc37_{event}_v1'/f'ops_input_{cycle}_v2';assert ops.is_dir()
  env=dict(os.environ,GC37_EVENT=event,GC37_OPS_ROOT=str(ops))
  check(math.ceil(n_wps*WPS_REF*1.2),label+':before_wps',ledger)
  run([sys.executable,str(HERE/'build_gc37_wps_crc_cpu_r1r2_v2.py'),'--cycle',cycle,'--arm','GFS','--raw-dir',str(raw)],env=env)
  outputs=json.loads((ops/f'WPS_{cycle}_GFS_REPORT.json').read_text());assert len(outputs)==n_wps
  for entry in outputs:
   p=BASE/f'drivers_gc37_{event}_v1'/entry['file'];assert p.is_file() and digest(p)==entry['sha256'],p
  check(0,label+':before_cleanup',ledger)
  for rec in rows:
   p=raw/rec['url'].rsplit('/',1)[-1]
   assert p.is_file() and p.stat().st_size==rec['download']['bytes']
   assert digest(p)==rec['sha256']==rec['download']['sha256'];p.unlink()
  # Independent source-redownload comparison is retained as evidence, not a GRIB input.
  assert all(p.name.endswith('.redownload_v3') for p in raw.iterdir())
  if not list(raw.iterdir()):raw.rmdir()
  ledger['cycles'].append({'cycle':cycle,'event':event,'lead':lead,'verified_files':len(rows),'wps_files':len(outputs),'raw_deleted_after_verification':True})
  (ROOT/f'DISK_LEDGER_{a.phase}_v3.json').write_text(json.dumps(ledger,indent=2))
  print('CYCLE_READY',label,ledger['peak_bytes'],flush=True)
 save(ROOT/f'INPUT_NETCDF_MANIFEST_{a.phase}_v3.json',manifest)
 save(ROOT/f'INPUT_R1R2_{a.phase}_v3_SUMMARY.json',{'phase':a.phase,'all_pass':True,'cycles':ledger['cycles'],'peak_bytes':ledger['peak_bytes'],'cap_bytes':CAP,'disk_ledger':str(ROOT/f'DISK_LEDGER_{a.phase}_v3.json')})
 print('PHASE_READY',a.phase,len(chosen),flush=True)
if __name__=='__main__':main()
