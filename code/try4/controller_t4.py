#!/usr/bin/env python3
"""T4 one-use Colab owner with fail-closed smoke and bytewise baseline gates."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time,traceback,csv
import numpy as np
R=Path(__file__).resolve().parent;CFG=R/'sessions-t4-try4.json';NAME='luw-r214a-t4-try4-1116'
B=['colab','--auth','oauth2','--config',str(CFG)]
T3=R.parent.parent/'R21.4a_T3_emptyground/T3d/dx1p0_s107_thin.npz'
rate=6.81;created=False;start=deadline=None;ambiguous=False
EVENT=R/'controller_t4_events.jsonl'
def event(kind,**kw):
 row={'event':kind,'epoch':time.time(),'session':NAME,'start_epoch':start,'deadline_epoch':deadline,**kw}
 with EVENT.open('a') as f:f.write(json.dumps(row)+'\n')
 (R/'controller_t4_state.json').write_text(json.dumps(row,indent=2)+'\n')
 print(kind,kw,flush=True)
def cmd(args,timeout=120,check=True):
 p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
 output=p.stdout+'\n'+p.stderr
 output=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',output)
 event('cli',args=args,rc=p.returncode,tail=output[-450:])
 if check and p.returncode:raise RuntimeError(f'CLI return {p.returncode}: '+output[-450:])
 return output
def cli(*args,timeout=120,check=True):return cmd(B+list(args),timeout,check)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def reconcile(stage):
 global ambiguous
 event('ambiguous_exec',stage=stage)
 for _ in range(3):
  try:
   status=cli('status','-s',NAME,timeout=60,check=False)
   sessions=cmd(['colab','--auth','oauth2','sessions'],timeout=60,check=False)
   if NAME not in sessions:raise RuntimeError('session absent')
   probe=cli('exec','-s',NAME,'-f',str(R/'check_t4.py'),timeout=90,check=False)
   if 'T4_PROBE' in probe:return probe
  except BaseException as e:event('reconcile_error',stage=stage,error=str(e)[-200:])
  time.sleep(25)
 ambiguous=True;raise RuntimeError('remote state ambiguous; do not relaunch or stop before deadline')
def ex(script,*args,stage='read',timeout=100):
 try:return cli('exec','-s',NAME,'-f',str(R/script),*args,timeout=timeout)
 except subprocess.TimeoutExpired:
  probe=reconcile(stage)
  if stage in ('launch','ack'):return probe
  return probe
def ack(kind,value):
 result=ex('ack_t4.py','--env',f'T4_ACK_KIND={kind}','--env',f'T4_ACK_VALUE={value}',stage='ack')
 if f'T4_ACK {kind}' not in result:
  probe=ex('check_t4.py');assert 'T4_PROBE' in probe
 event('ack',kind=kind,value=value)
def download(remote,local,timeout=180):
 target=R/local
 if target.exists():return target
 cli('download','-s',NAME,remote,str(target),timeout=timeout)
 assert target.is_file() and target.stat().st_size>0
 return target
def thin(case,size,digest):
 p=download(f'/content/t4_out/{case}_thin.npz',f'{case}_thin.npz',timeout=250)
 assert p.stat().st_size==size and sha(p)==digest,(case,'hash/size mismatch')
 (R/f'{case}_thin.sha256').write_text(digest+'\n')
 event('thin_verified',case=case,sha256=digest,bytes=size)
 ack(case,digest)
def smoke_gate():
 log=download('/content/t4_out/smoke_solver.log','smoke_solver.log')
 for remote,local in [('/content/t4_out/smoke_results_listing.txt','smoke_results_listing.txt'),('/content/t4_out/smoke_wall_tau_raw.csv','smoke_wall_tau_raw.csv'),('/content/t4_out/smoke_ground_eligibility.csv','smoke_ground_eligibility.csv'),('/content/t4_out/wall_gate0.csv','wall_gate0.csv'),('/content/t4_out/wall_gate0_solver.log','wall_gate0_solver.log')]:download(remote,local)
 with (R/'smoke_ground_eligibility.csv').open() as f:eligible=list(csv.DictReader(f))[0]
 measured=int(eligible['measured']);expected=int(eligible['expected_interior'])
 assert measured>0 and measured>=expected*0.8,(measured,expected)
 tau=download('/content/t4_out/smoke_wall_tau.csv','smoke_wall_tau.csv')
 monitor=download('/content/stage_t4/smoke/RESULTS/city_stability.csv','smoke_city_stability.csv')
 exitfile=download('/content/t4_out/smoke_exit.json','smoke_exit.json')
 assert json.loads(exitfile.read_text())['exit']==0
 with tau.open() as f:rows=list(csv.DictReader(f))
 valid=[r for r in rows if float(r['count'])>0]
 ustars=[float(r['ustar_mps']) for r in valid]
 stresses=[float(r['tau_abs_over_rho_lattice']) for r in valid]
 assert valid and all(np.isfinite(ustars)) and all(np.isfinite(stresses)) and max(ustars)>0
 with monitor.open() as f:trace=list(csv.DictReader(f))
 assert len(trace)>2
 assert all(np.isfinite(float(r['mass_fluid'])) and np.isfinite(float(r['max_u_lattice'])) for r in trace)
 assert not any(re.search(r'\b(?:nan|inf)\b',r['first_nonfinite_xyz_component'],re.I) for r in trace)
 mass0=float(trace[0]['mass_fluid']);mass1=float(trace[-1]['mass_fluid']);drift=abs(mass1/mass0-1)
 metrics={'tau_over_rho_lattice_minmax':[min(stresses),max(stresses)],'ustar_mps_minmax':[min(ustars),max(ustars)],'open_domain_mass_inventory_relative_change':drift,'mass_inventory_note':'Open inflow/outflow: change is not a closed-domain conservation residual. Link packet conservation requires separate GPU fixture.','monitor_rows':len(trace),'solver_exit':0}
 fixture=download('/content/t4_out/gpu_link_fixture.json','gpu_link_fixture.json')
 gpu_audit=json.loads(fixture.read_text())
 assert gpu_audit['gpu_packet_mapping_fixture']=='PASS'
 assert len(gpu_audit['parities'])==2
 assert all(r['relative_mass_error']<=1e-6 and r['normal_momentum_plus_wall_reaction_residual']<=1e-6 for r in gpu_audit['parities'])
 metrics['gpu_packet_fixture_sha256']=sha(fixture)
 (R/'smoke_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
 event('smoke_checked',**metrics)
 # Link-level ledger and mask-transition permutations were checked independently
 # before allocation (audit_linked_mirror_final.json); open-domain inventory is
 # explicitly not used as a conservation claim. A solver-level closed-box mass
 # test is still pending and must be reported as such.
 assert (R/'audit_linked_mirror_final.json').exists()
 audit=json.loads((R/'audit_linked_mirror_final.json').read_text())
 assert audit['static_address_audit']=='PASS' and audit['mass_normal_flux_ledger'].startswith('PASS')
 return metrics
def main():
 global created,start,deadline
 assert not (R/'.colab_owner').exists()
 sessions=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
 assert NAME not in sessions,'session already owned'
 with (R/'.colab_owner').open('x') as f:f.write('T4 retry #050ea7a4 '+NAME+' '+str(time.time())+'\n')
 bundle=R/'stage_t4_v4.tar.gz';assert bundle.exists()
 allocation_start=time.time();allocation_end=allocation_start+4*3600;attempt=0
 while time.time()<allocation_end and not created:
  attempt+=1
  for gpu in ('A100','G4'):
   if time.time()>=allocation_end:break
   event('allocation_attempt',attempt=attempt,gpu=gpu,local_time=time.strftime('%m-%d %H:%M:%S %Z'))
   try:
    cli('new','-s',NAME,'--gpu',gpu,timeout=130)
    created=True;start=time.time();event('allocation_success',attempt=attempt,gpu=gpu,local_time=time.strftime('%m-%d %H:%M:%S %Z'))
    break
   except BaseException as e:
    # Never repeat an ambiguous allocation when a session might exist.
    view=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
    if NAME in view:raise RuntimeError('allocation ambiguous: named session listed; do not retry') from e
    if isinstance(e,subprocess.TimeoutExpired):raise RuntimeError('allocation timeout: session absent in single read; do not retry') from e
    if not re.search('503|412|Service Unavailable|Allocation refused',str(e),re.I):raise
    event('allocation_refused',attempt=attempt,gpu=gpu,local_time=time.strftime('%m-%d %H:%M:%S %Z'),reason=str(e)[-400:])
  if not created and time.time()<allocation_end:
   until=min(allocation_start+attempt*1200,allocation_end)
   event('allocation_backoff',next_epoch=until)
   time.sleep(max(0,until-time.time()))
 if not created:
  event('allocation_exhausted',attempts=attempt,elapsed_s=time.time()-allocation_start)
  raise RuntimeError('4h allocation window exhausted without GPU session')
 deadline=start+(23/rate)*3600
 for local,remote in [(bundle,'/content/t4_stage.tar.gz'),(R/'remote_worker_t4.py','/content/t4_worker.py'),(R/'gpu_link_fixture.py','/content/t4_gpu_link_fixture.py'),(R.parent.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py','/content/t3_parser.py')]:
  cli('upload','-s',NAME,str(local),remote,timeout=180)
 output=ex('launch_t4.py','--env',f'T4_BUNDLE_SHA={sha(bundle)}','--env',f'T4_DEADLINE={deadline}',stage='launch',timeout=160)
 if 'T4_LAUNCHED_PID' not in output:
  assert 'T4_PROBE' in output and 'LOGTAIL' in output,'launch not confirmed; no retry'
 keep=[str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t4.log','--proc','t4_worker.py','--stale-min','180','--until-marker','/content/t4_out/run.done','--final-pull','/content/t4_out/*.json:'+str(R/'final'),'--expect-hours','4','--max-hours','5','--no-remind','--detach']
 event('keepalive',output=cmd(keep,timeout=100)[-600:])
 acked=set();smoke=False
 while time.time()<deadline-700:
  state=ex('check_t4.py',timeout=110)
  if 'failed True' in state:raise RuntimeError('remote worker failed: '+state[-1000:])
  if 'smoke True' in state and not smoke:
   smoke_gate();smoke=True
   ack('smoke','ok')
  for case,size,digest in re.findall(r'THIN\s+(\S+)_thin\.npz\s+(\d+)\s+([0-9a-f]{64})',state):
   if case not in acked:thin(case,int(size),digest);acked.add(case)
  if 'off_s107' in acked and not (R/'baseline_comparison.json').exists():
   with np.load(T3,allow_pickle=False) as a, np.load(R/'off_s107_thin.npz',allow_pickle=False) as b:
    same={k:bool(np.array_equal(a[k],b[k])) for k in ('u_avg','fluid')}
    shape={k:[a[k].shape,b[k].shape] for k in ('u_avg','fluid')}
   record={'arrays_equal':same,'shapes':shape,'reference_sha256':sha(T3),'off_sha256':sha(R/'off_s107_thin.npz')}
   (R/'baseline_comparison.json').write_text(json.dumps(record,indent=2)+'\n')
   assert all(same.values()),'Stage A bitwise mismatch: halt before B'
   ack('baseline_gate','PASS')
  if 'done True' in state:
   assert len(acked)==4;event('completed',acked=sorted(acked));return
  time.sleep(45)
 raise RuntimeError('CU deadline guard triggered')
def stop():
 if not created:return
 if ambiguous and time.time()<deadline-350:event('stop_deferred_ambiguous');return
 for remote,local in [('/content/t4.log','remote_t4.log'),('/content/t4_out/build_off.log','build_off.log'),('/content/t4_out/build_on.log','build_on.log'),('/content/t4_out/build_gate0.log','build_gate0.log'),('/content/t4_out/wall_gate0.csv','wall_gate0.csv'),('/content/t4_out/wall_gate0_solver.log','wall_gate0_solver.log'),('/content/t4_out/run.failed','run.failed')]:
  try:download(remote,local)
  except Exception as e:event('missing_evidence',file=local,error=str(e)[-200:])
 for case in ('smoke','off_s107','wm_s107','wm_s108','wm_s109'):
  for suffix in ('_solver.log','_exit.json','_geometry_gate.csv','_thin_meta.json','_wall_tau.csv','_wall_tau_raw.csv','_ground_eligibility.csv','_results_listing.txt','_city_stability.csv'):
   try:download(f'/content/t4_out/{case}{suffix}',f'{case}{suffix}')
   except Exception:pass
 try:cli('stop','-s',NAME,timeout=120);event('stopped',estimated_CU=(time.time()-start)*rate/3600)
 except Exception as e:event('stop_error',error=str(e)[-300:])
 try:view=cmd(['colab','--auth','oauth2','sessions'],timeout=60);event('stop_confirmed',absent=NAME not in view)
 except Exception as e:event('stop_check_error',error=str(e)[-200:])
 cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],timeout=30,check=False)
if __name__=='__main__':
 try:main();event('controller_finished',success=True);rc=0
 except BaseException:event('controller_failed',trace=traceback.format_exc()[-2000:]);rc=2
 finally:stop()
 sys.exit(rc)
