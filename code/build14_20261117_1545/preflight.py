import ast,csv,hashlib,json,pathlib,shutil,tempfile,tarfile,sys,io,contextlib
import controller as c
R=c.R
names=c.PAYLOAD+['controller.py','probe_gate.py','launch_gate.py','machine.py']
for n in names:
 if n.endswith('.py'):compile((R/n).read_text(),n,'exec')
for pkg,mf,root in [('t9b12_source.tar.gz','t9b12_manifest.json','FluidX3D_facade_v11'),('t9b2_stage.tar.gz','t9b2_archive.json','stage')]:
 m=json.loads((R/mf).read_text());assert c.sha(R/pkg)==m['archive_sha256']
 with tarfile.open(R/pkg) as t:
  for n,h in m['members'].items():assert hashlib.sha256(t.extractfile(f'{root}/{n}').read()).hexdigest()==h,n
  if root=='stage':
   raw=t.extractfile('stage/case/conf.luwpf').read().decode(); assert raw.count('run_nstep = 31000')==raw.count('purge_avg = 20000')==1
   test=raw.replace('run_nstep = 31000','run_nstep = 2000').replace('purge_avg = 20000','purge_avg = 1000');assert 'run_nstep = 2000' in test and 'purge_avg = 1000' in test
w=(R/'worker_gate.py').read_text(); assert "for wall in ('y',):" in w and "stage_A_verdict.json" in w and "run.done" in w
p=(R/'probe_gate.py').read_text()
trace=c.R.parent/'build12_20261117_145427/evidence/channel_x_on_trace.csv'
a=ast.parse(w); ns={'csv':csv};exec(compile(ast.Module([n for n in a.body if isinstance(n,ast.FunctionDef) and n.name=='analyze'],[]),'<trace_reader>','exec'),ns)
assert len(ns['analyze'](trace,True))==1001
with tempfile.TemporaryDirectory(dir=R) as z:
 root=pathlib.Path(z);out=root/'out';out.mkdir();dest=root/'dest';dest.mkdir(); f=out/'channel_y_on_trace.csv';shutil.copyfile(trace,f); (out/(f.name+'.sha256')).write_text(c.sha(f)+'\n')
 buf=io.StringIO()
 with contextlib.redirect_stdout(buf):exec(p.replace("'/content/t9b14",repr(z)[:-1]),{})
 data=json.loads(buf.getvalue().removeprefix('PROBE '));assert not data['done'] and not data['failed']
 def fake(args,t):
  assert args[0]=='download';shutil.copyfile(out/pathlib.Path(args[1]).name,args[2]);return 0,''
 v=c.pull(fake,dest,f.name,data['ready'][f.name]);assert v==c.sha(f)
 assert not c.REQUIRED<={f.name}
 print('Exact probe and controller pull verified both data and full-basename sidecar; production-shaped trace schema OK (archived x fixture, not a y result).')
print('Source/package members, city configuration rewrite, all Python syntax, and y-only stage order verified. No GPU result inferred.')
with (R/'PREFLIGHT.ok').open('x') as f:json.dump({n:c.sha(R/n) for n in names},f)
