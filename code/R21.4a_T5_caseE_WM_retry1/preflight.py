#!/usr/bin/env python3.10
"""No solver: archive, code, timeout, ACK, sampler, metric contracts."""
import pathlib,json,tarfile,hashlib,importlib.util,subprocess,sys,tempfile,os,csv,types
import numpy as np
R=pathlib.Path(__file__).resolve().parent
for n in ('worker.py','controller.py','launch.py','probe.py','ack.py','analyze.py','gpu_probe.py'):
 subprocess.run([sys.executable,'-m','py_compile',str(R/n)],check=True)
spec=importlib.util.spec_from_file_location('controller',R/'controller.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
assert c.sha(R/'stage_t5.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
with tarfile.open(R/'stage_t5.tar.gz') as t:
 names=t.getnames();assert 'stage/manifest.json' in names and all(n=='stage' or n.startswith('stage/') for n in names)
man=json.loads((R/'stage/manifest.json').read_text());assert len(man['cases'])==4
for mode in ('on','off'):
 for n,h in man['source'][mode].items():assert c.sha(R/f'stage/FluidX3D_{mode}/src'/n)==h
for label,item in man['cases'].items():assert c.sha(R/'stage/cases'/label/'conf.luwpf')==item['config_sha256']
assert (R/'stage/FluidX3D_on/src/defines.hpp').read_text().count('#define GROUND_WALL_MODEL // T4')==1
assert (R/'stage/FluidX3D_off/src/defines.hpp').read_text().count('//#define GROUND_WALL_MODEL // T5')==1
print('ARCHIVE_SOURCE_CONFIG_IMPORT_PASS',len(names),flush=True)
# Inject a timeout into the real controller branch; stop is trapped.
events=[];c.log=lambda ev,**kw:events.append(ev);c.cmd=lambda *a,**kw:('IDLE',0);c.stop=lambda reason: (_ for _ in ()).throw(AssertionError('unexpected stop'))
c.ENDPOINT='gpu-a100-s-test'
def timeout():raise subprocess.TimeoutExpired('read-only probe',110)
state,absent=c.monitor_once(timeout,lambda:True,lambda _:None)
assert state is None and absent is False and events==['probe_error','named_status','global_reconcile']
print('PROBE_TIMEOUT_CONTINUES_NO_STOP',events,flush=True)
# Exact ACK script in isolated filesystem fixture, including dual SHA.
with tempfile.TemporaryDirectory(dir=R) as td:
 root=pathlib.Path(td);label='E_s101_off';vals=('a'*64,'b'*64)
 for ext,h in zip(('thin.npz','points80.json'),vals):
  (root/f'{label}_{ext}.sha256').write_text(h+'\n');(root/f'{label}_{ext}').write_bytes(b'fixture')
 src=(R/'ack.py').read_text().replace("pathlib.Path('/content/t5_out')",'pathlib.Path('+repr(td)+')')
 env={**os.environ,'T5_ACK_LABEL':label,'T5_ACK_PAIR':' '.join(vals)}
 p=subprocess.run([sys.executable,'-c',src],env=env,capture_output=True,text=True,check=True)
 assert p.stdout.strip()=='ACK '+label and (root/f'{label}.ack').read_text().strip()==' '.join(vals)
 print('DUAL_SHA_ACK_PASS',p.stdout.strip(),flush=True)
# Synthetic array fixture uses the exact point sampler and metric analyzer independently of solver.
parser=R.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py';sys.path.insert(0,str(parser.parent));sys.modules['remote_worker_run2']=__import__('remote_worker_run2')
spec=importlib.util.spec_from_file_location('worker',R/'worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
ref=json.loads((R/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80
v={'dims':(500,500,270),'origin':(0.,0.,-20.),'spacing':(1.,1.,1.),'fields':{'speed_mean':np.ones((2,2,2),dtype='f4'),'fluid':np.ones((2,2,2),dtype='f4')}}
class Constant:
 def __getitem__(self,idx):return 2.0
v['fields']={'speed_mean':Constant(),'fluid':Constant()};assert abs(w.sampled(v,ref['rows'][0])['Su']-2)<1e-12
widths=list(csv.DictReader((R/'widths.csv').open()));assert len(widths)==80 and sum(x['width_min_m']!='' and float(x['width_min_m'])>=15 for x in widths)==64
print('SAMPLER_80_WIDTH64_PASS',flush=True)
with tempfile.TemporaryDirectory(dir=R) as td:
 d=pathlib.Path(td);(d/'evidence').mkdir();(d/'widths.csv').write_bytes((R/'widths.csv').read_bytes())
 for seed in (101,102):
  for mode in ('off','on'):
   label=f'E_s{seed}_{mode}';rows=[{'id':int(p['id']),'obs':float(p['after']),'Su_ratio':float(p['after']),'xyz_m':[1.,2.,2.5],'solid_weight':0.0} for p in ref['rows']]
   q=d/'evidence'/f'{label}_points80.json';q.write_text(json.dumps({'label':label,'uref':3.9286416,'rows':rows}))
   (d/'evidence'/f'{label}_points80.json.sha256').write_text(hashlib.sha256(q.read_bytes()).hexdigest())
 spec=importlib.util.spec_from_file_location('analyze',R/'analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);a.R=d;a.E=d/'evidence';a.main()
 assert json.loads((d/'T5_verdict.json').read_text())['verdict']=='在种子变化内'
 print('PAIRED_ANALYZER_FIXTURE_PASS',flush=True)
