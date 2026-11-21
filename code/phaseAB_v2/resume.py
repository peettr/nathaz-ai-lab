#!/usr/bin/env python3
"""Resume ONLY the already-created phaseAB session; no allocation or relaunch."""
import pathlib,subprocess,json,time,hashlib,traceback,re
R=pathlib.Path(__file__).resolve().parent; O=R/'evidence';CFG=R/'sessions.json';NAME='luw-r214a-t4-phaseab-v2-1116';EP='gpu-a100-s-usc1c0-4989kh7iqdg7';EV=R/'resume_events.jsonl'
LOCAL=['colab','--auth','oauth2','--config',str(CFG)];PREFIX=['A_dx1p0_s107','B_dx1p0_s107','B_dx1p0_s108','B_dx1p0_s109']
def log(event,**kw):
 with EV.open('a') as f:f.write(json.dumps({'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':event,**kw})+'\n')
def cmd(args,check=True):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=115)
 if check and p.returncode:raise RuntimeError(f'{args[:6]} rc={p.returncode} {p.stdout[-600:]}')
 return p.stdout
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def execfile(p,env=None):
 a=LOCAL+['exec','-s',NAME,'-f',str(p)]
 for k,v in (env or {}).items():a+=['--env',k+'='+str(v)]
 return cmd(a)
def pull(label,name):
 dest=O/f'{label}_{name}'
 if not dest.exists():cmd(LOCAL+['download','-s',NAME,f'/content/phaseab_out/{label}_{name}',str(dest)])
 assert dest.is_file() and dest.stat().st_size>0
 return dest
processed=set(); deadline=1794867000.6094275+min(2.2,10/5.4)*3600
try:
 assert EP in cmd(['colab','--auth','oauth2','sessions']),'owned endpoint missing'
 log('resume',endpoint=EP)
 while time.time()<deadline-180:
  out=execfile(R/'probe.py');line=next((x for x in out.splitlines() if x.startswith('PROBE ')),None)
  assert line,out[-500:];state=json.loads(line[6:]);log('probe',ready=list(state['ready']),tail=state['log'][-250:],failed=state['failed'])
  for label in PREFIX:
   key=label+'_thin.sha256'
   if key not in state['ready'] or label in processed:continue
   expected=state['ready'][key]['sha'];npz=pull(label,'thin.npz');assert npz.stat().st_size==state['ready'][key]['size'] and sha(npz)==expected
   assert pull(label,'thin.sha256').read_text().strip()==expected
   for name in ('thin_meta.json','exit.json','geometry_gate.csv','solver.log'):pull(label,name)
   if label.startswith('B_'):
    for name in ('ground_excluded.csv','ground_eligibility.csv','wall_tau_actual.csv','city_stability.csv','actual_opencl.cl'):pull(label,name)
   same=True
   if label.startswith('A_'):
    import numpy as np
    baseline=R.parent.parent/'R21.4a_T3_emptyground/T3d/dx1p0_s107_thin.npz'
    assert sha(baseline)==json.loads((R/'stage/phase_manifest.json').read_text())['baseline_thin_sha256']
    with np.load(npz,allow_pickle=False) as a,np.load(baseline,allow_pickle=False) as b:
     same=all(a[k].dtype==b[k].dtype and a[k].shape==b[k].shape and np.array_equal(a[k],b[k]) for k in ('u_avg','fluid'))
     gate={'bitwise_equal':bool(same),'array_shapes':{k:list(a[k].shape) for k in ('u_avg','fluid')},'baseline_sha256':sha(baseline),'candidate_sha256':expected}
    (O/'A_verdict.json').write_text(json.dumps(gate,indent=2)+'\n')
   ack=R/'ack_resume.py'
   if not ack.exists():ack.write_text("import pathlib,os\nr=pathlib.Path('/content/phaseab_out');k=os.environ['ACK_LABEL'];v=os.environ['ACK_SHA'];assert (r/(k+'_thin.sha256')).read_text().strip()==v\n(r/(k+'.ack')).write_text(v)\nif k.startswith('A_'):(r/'A_verdict.json').write_text(os.environ['A_VERDICT'])\nprint('ACK',k)\n")
   execfile(ack,{'ACK_LABEL':label,'ACK_SHA':expected,'A_VERDICT':json.dumps({'bitwise_equal':bool(same)})})
   processed.add(label);log('host_verified',label=label,sha=expected,bitwise_equal=same)
  if state['done'] or state['failed'] or state['stopped_A']:break
  time.sleep(25)
 if state['failed']:raise RuntimeError(state['log'][-700:])
 log('terminal',processed=list(processed),state=state)
except BaseException as e:log('error',error=str(e),traceback=traceback.format_exc()[-2000:]);print('RESUME_ERROR',e,flush=True)
finally:
 try:
  for remote in ('/content/phaseab.log','/content/phaseab_out/run.failed','/content/phaseab_out/run.done','/content/phaseab_out/run.stopped_A'):
   dest=O/pathlib.Path(remote).name
   if not dest.exists():cmd(LOCAL+['download','-s',NAME,remote,str(dest)],False)
  cmd(LOCAL+['stop','-s',NAME],False)
  after=cmd(['colab','--auth','oauth2','sessions']);log('stop_check',endpoint_absent=EP not in after,sessions=after[-700:])
 except BaseException as e:log('stop_error',error=str(e))
print('RESUME_FINISHED',list(processed),flush=True)
