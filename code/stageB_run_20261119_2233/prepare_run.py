import pathlib,shutil,json,hashlib,difflib
R=pathlib.Path(__file__).resolve().parent
B=R.parent/'stageB_native_v2_20261119_2140'
for n in ('t17b_stage.tar.gz','t17b_manifest.json','native_analysis.py','assert_T17.py','remote_B.py','machine.py','SESSION_PLAN.json','NATIVE_PRODUCER_APPROVED.ok'):
 shutil.copy2(B/n,R/n)
w=(B/'worker_native.py').read_text()
w=w.replace('from assert_T17 import evaluate,seed_metrics\n','')
w=w.replace("order=(('t15','1'),) if mode=='smoke' else tuple((g,s) for g in GROUPS for s in SEEDS)","order=(('t15','1'),('t15','2'),('t4','1'),('t4','2'),('bounce','1'),('bounce','2'))")
w=w.replace("    seed_metrics(result)\n    x=OUT/(label+'_case.json');x.write_text(json.dumps(result)+'\\n');seal(x)","    validate_contract(result)\n    x=OUT/(label+'_case.json');x.write_text(json.dumps(result,allow_nan=False)+'\\n');seal(x)")
# Remove scientific work from worker and require only the structural contract
w=w.replace("  if mode=='production':\n   data={'schema':'T17-B-v1','cases':cases};result=evaluate(data)\n   x=OUT/'T17_result.json';x.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\\n');seal(x)\n",'')
w=w.replace('  if mode==\'smoke\':','  if mode==\'smoke\':')
# smoke code references frozen evaluator but production cannot enter it; eliminate entire branch
start=w.index("   if mode=='smoke':\n",w.index("   if not (d/'producer.done')"))
end=w.index('   # Compact evidence only:',start)
w=w[:start]+"   result=summarize(d)\n   validate_contract(result)\n   x=OUT/(label+'_case.json');x.write_text(json.dumps(result,allow_nan=False)+'\\n');seal(x)\n   cases[group][seed]=result\n"+w[end:]
w=w.replace("  done=OUT/'run.done'", "  done=OUT/'run.done'")
# Fail closed if a summary lacks any required structural field; no scientific V0 judgement here.
anchor='def run(c=C):\n'
validate='''def validate_contract(r):
 import math
 if set(r)<{'v0_attempts','stress','blocks','correlations','profile_u','native_provenance'}:raise ValueError('contract missing fields')
 if len(r['profile_u'])!=64 or set(r['profile_u'])!={str(k) for k in range(1,65)}:raise ValueError('contract requires 64 levels')
 if len(r['blocks'])!=4 or not r['v0_attempts']:raise ValueError('contract blocks/V0')
 if float(r['stress']['tau_x_time_mean'])<=0:raise ValueError('tau_x must be positive drag')
 def walk(x):
  if isinstance(x,dict):return all(walk(y) for y in x.values())
  if isinstance(x,list):return all(walk(y) for y in x)
  if isinstance(x,(float,int)):return math.isfinite(x)
  return isinstance(x,str)
 if not walk(r):raise ValueError('nonfinite contract')
 return True

'''
w=w.replace(anchor,validate+anchor)
w=w.replace("  if mode=='smoke'", "  if mode=='smoke'")
w=w.replace("  if mode=='smoke':", "  if mode=='smoke':")
w=w.replace("  if mode=='smoke'", "  if mode=='smoke'")
# native producer still accepts production; fixture uses production mode.
(R/'worker_native.py').write_text(w)
c=(B/'controller_native.py').read_text()
c=c.replace("mode=os.environ.get('T17_B_RUN_MODE','smoke')", "mode='production'")
c=c.replace("cases=('t15_s1',) if mode=='smoke' else ALL_CASES", "cases=('t15_s1','t15_s2','t4_s1','t4_s2','bounce_s1','bounce_s2')")
c=c.replace("and ('smoke_pipeline.json' if mode=='smoke' else 'T17_result.json') in verified", "and all(x+'_case.json' in verified for x in cases)")
c=c.replace("cap=.6 if mode=='smoke' else 3.5", "cap=3.5")
c=c.replace("required=(2800/plan['steps_per_second']['t15']+90) if mode=='smoke' else plan['worst_case_solver_s']+plan['fixed_overhead_s']", "required=plan['worst_case_solver_s']+plan['fixed_overhead_s']")
c=c.replace("'--max-hours','2'", "'--max-hours','1'")
# mark failed whether an exception is observed, but do not stop until evidence is verified/deadline
(R/'controller_native.py').write_text(c)
# clone a fixture stub with proper 5T/optional extension and 2T data per case
stub='''#!/usr/bin/env python3
"""Synthetic solver only; not physics evidence. Exercise real worker and V0 branches."""
import os,pathlib,csv,math,time,numpy as np
p=pathlib.Path(os.environ['T17_B_DIR']);p.mkdir(exist_ok=True)
seed=os.environ['T17_B_SEED'];group=p.name.split('_s')[0]
half=200;stride=50;initial=2000
with (p/'timing.csv').open('w') as f:
 f.write('attempt,equilibrium_end_step,passed,half_T_steps,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\\n')
 f.flush()
 def v0(a,end):
  f.write(f'{a},{end},pending,{half},0.01282051,78,32768,{stride},production\\n');f.flush()
  (p/f'v0_{a}.ready').write_text(str(end)+'\\n')
  for _ in range(1000):
   if (p/f'v0_{a}.decision').exists():return (p/f'v0_{a}.decision').read_text().strip()
   time.sleep(.01)
  raise RuntimeError('no V0 response')
 with (p/'ledger.csv').open('w') as l:
  l.write('step,mass_lattice,px_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\\n')
  for step in range(0,4001,50):
   # seed 2 initially fails V0, then a second window passes.
   px=100+(step/2000)*10 if seed=='2' and step<=2000 else (110 if seed=='2' else 100)
   l.write(f'{step},2097152,{px},0.42,{step*.42},1\\n')
 (p/'ledger.csv').flush() if False else None
 first=v0(0,2000)
 if seed=='2':
  assert first=='extend',first
  second=v0(1,2400);assert second=='pass',second
  start=2400
 else:
  assert first=='pass',first
  start=2000
(p/'statistics_start.txt').write_text(str(start)+'\\n')
with (p/'profiles.csv').open('w') as f:
 f.write('step,k,u_x_mean_si\\n')
 for step in range(start+50,start+800+1,50):
  for k in range(1,65):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   f.write(f'{step},{k},{u:.12g}\\n')
x=np.arange(256)[None,:];y=np.arange(128)[:,None]
with (p/'planes.bin').open('wb') as f:
 for j in range(16):
  for k in (3,10):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   fluct=.3*np.sin(2*np.pi*x/256+j*.1)+.2*np.sin(2*np.pi*y/128+j*.05)
   a=np.empty((128,256,3),dtype='<f4');a[:,:,0]=u+fluct;a[:,:,1]=.4*fluct;a[:,:,2]=.2*fluct;f.write(a.tobytes())
(p/'producer.done').write_text(str(start+800)+'\\n')
print('SYNTHETIC_FIXTURE_ONLY',group,seed,first,flush=True)
'''
(R/'stub_native.py').write_text(stub)
for n in ('worker_native.py','controller_native.py'):
 a=(B/n).read_text().splitlines(True);b=(R/n).read_text().splitlines(True)
 (R/(n+'.diff')).write_text(''.join(difflib.unified_diff(a,b,fromfile=str(B/n),tofile=str(R/n))))
manifest={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ('worker_native.py','controller_native.py','native_analysis.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json')}
(R/'SOURCE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
