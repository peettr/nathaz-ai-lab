import hashlib,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile,time
import controller as c
r=c.R
names=sorted((set(c.PAYLOAD)-{c.BUDGET_FILE})|{'controller.py','launch_gate.py','probe_gate.py','machine.py','dry_stub.py','real_worker_preflight.py','replay_build14.py'})
assert not (r/'PREFLIGHT.ok').exists()
for n in names:
 if n.endswith('.py'):compile((r/n).read_text(),n,'exec')
for arc,man,root in [('t9b12_source.tar.gz','t9b12_manifest.json','FluidX3D_facade_v11'),('t9b2_stage.tar.gz','t9b2_archive.json','stage')]:
 meta=json.loads((r/man).read_text());assert c.sha(r/arc)==meta['archive_sha256']
 if root.startswith('Fluid'):assert meta['archive_sha256']=='13bc199a005cfdf99cb7e81de79382676fcc4c2479e6abcc35ff4ef9296be9aa'
 with tarfile.open(r/arc) as t:
  assert {m.name for m in t if m.isfile()}=={f'{root}/{n}' for n in meta['members']}
  for n,h in meta['members'].items():assert hashlib.sha256(t.extractfile(f'{root}/{n}').read()).hexdigest()==h
  if root=='stage':
   cfg=t.extractfile('stage/case/conf.luwpf').read().decode();assert cfg.count('run_nstep = 31000')==cfg.count('purge_avg = 20000')==1
sandbox=r/'dry_fixture';sandbox.mkdir(); content=sandbox/'content';content.mkdir()
for n in c.PAYLOAD:
 if n==c.BUDGET_FILE:
  now=time.time();(content/n).write_text(json.dumps(dict(created=now,deadline=now+2500,assumed_CU_per_h=c.rate)))
 else:shutil.copyfile(r/n,content/n)
assert sorted(x.name for x in content.iterdir())==sorted(c.PAYLOAD)
print('PAYLOAD ONLY:',sorted(c.PAYLOAD),flush=True)
# Run the exact bytes uploaded to Colab at literal /content/worker_gate.py.
cmd=['bwrap','--tmpfs','/','--ro-bind','/usr','/usr','--ro-bind','/etc','/etc','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(content),'/content','--ro-bind',str(r/'dry_stub.py'),'/stub.py','--setenv','T9B_PREFLIGHT_SOLVER','/stub.py','--chdir','/content']
p=subprocess.run(cmd+['/usr/bin/python3','/content/worker_gate.py']);print('worker local exit:',p.returncode,flush=True)
o=content/'t9b16/out'; required={'channel_y_off_trace.csv':1001,'channel_y_on_trace.csv':1001,'cube_off_trace.csv':301,'cube_on_trace.csv':301}
import csv
for n,count in required.items():
 f=o/n;rows=list(csv.DictReader(f.open())); assert [int(x['step']) for x in rows]==list(range(count)); print('VERIFIED STUB FILE',n,count,c.sha(f),flush=True)
 assert (o/(n[:-10]+'.log')).read_text().startswith('STUB_INVOKED /content/t9b16/out/'+n)
assert p.returncode==1 and 'budget stop before B city full and two short runs' in (o/'run.failed').read_text()
v=json.loads((o/'stage_A_verdict.json').read_text());assert v['stage']=='A_passed' and all(x['passed'] for x in v['channels'].values()) and len(v['cube'])==2
for side in o.glob('*.sha256'):assert c.sha(o/side.name[:-7])==side.read_text().strip()
subprocess.run([sys.executable,str(r/'replay_build14.py')],check=True)
with (r/'PREFLIGHT.ok').open('x') as f:json.dump({n:c.sha(r/n) for n in names},f)
print('PASS: Build15 discrepancy reproduced; real Build16 worker ran the four expected solver invocations; validated evidence names/rows/full basename SHAs; expected B budget sentinel. No physics or GPU evidence.',flush=True)
