#!/usr/bin/env python3
"""No solver/Colab: exact package + scripts + probe/download/sha protocol fixture."""
import ast,hashlib,importlib.util,json,pathlib,subprocess,sys,tarfile,tempfile
R=pathlib.Path(__file__).resolve().parent
W=R/'worker_gate.py';C=R/'controller_gate.py';L=R/'launch_gate.py';P=R/'probe_gate.py'
for file in (W,C,L,P):
 subprocess.run([sys.executable,'-m','py_compile',str(file)],check=True)
for file in (W,C,L,P):ast.parse(file.read_text())
manifest=json.loads((R/'t9b11_manifest.json').read_text());arc=R/'t9b11_source.tar.gz'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(arc)==manifest['archive_sha256']
with tarfile.open(arc) as tar:
 members=tar.getmembers();assert all((m.name=='FluidX3D_facade_v10' or m.name.startswith('FluidX3D_facade_v10/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()) for m in members)
 with tempfile.TemporaryDirectory(dir=R) as d:
  tar.extractall(d,filter='data')
  for name,h in manifest['members'].items():assert sha(pathlib.Path(d)/'FluidX3D_facade_v10'/name)==h,name
with tarfile.open(R.parent/'t9b2_stage.tar.gz') as tar:
 names={m.name for m in tar.getmembers()}
 assert 'stage/case/conf.luwpf' in names and 'stage/B2u_reference_points.json' in names
 config=tar.extractfile('stage/case/conf.luwpf').read().decode();assert config.count('run_nstep = 31000')==1 and config.count('purge_avg = 20000')==1
 assert 'run_nstep = 2000' in config.replace('run_nstep = 31000','run_nstep = 2000')
 assert 'purge_avg = 1000' in config.replace('purge_avg = 20000','purge_avg = 1000')
 spec=importlib.util.spec_from_file_location('controller',C);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 with tempfile.TemporaryDirectory(dir=R) as d:
  fixture=pathlib.Path(d);(fixture/'out').mkdir()
  data=fixture/'out'/'channel_x_on_trace.csv';data.write_text('step,tangent_momentum\n0,1\n1000,1\n');(fixture/'out'/(data.name+'.sha256')).write_text(sha(data)+'\n')
  script=P.read_text().replace("pathlib.Path('/content/t9b11')",f"pathlib.Path({str(fixture)!r})").replace("pathlib.Path('/content/t9b11.launch')",f"pathlib.Path({str(fixture/'t9b11.launch')!r})").replace("pathlib.Path('/content/t9b11.log')",f"pathlib.Path({str(fixture/'t9b11.log')!r})")
  result=subprocess.run([sys.executable,'-c',script],text=True,capture_output=True,check=True).stdout
  state=json.loads(next(x[6:] for x in result.splitlines() if x.startswith('PROBE ')))
  info=state['ready'][data.name];assert info=={'sha':sha(data),'size':data.stat().st_size}
  dest=fixture/'pulled.csv';dest.write_bytes(data.read_bytes());assert dest.stat().st_size==info['size'] and sha(dest)==info['sha']
worker=W.read_text();controller=C.read_text()
assert 'FACADE_COUNT' not in worker
assert all(worker.count(x)>=1 for x in ('channel_{wall}','stage_A_verdict.json','city_2000_','city_2000_difference.json','run.done','run.failed'))
assert 'for state in (\'off\',\'on\'):' in worker and worker.index("stage_A_verdict.json")<worker.index("city_build_")<worker.index("city_2000_difference.json")
assert "deadline=created+4.5*3600/6.81" in controller and "--detach" in controller and "--final-pull" in controller
assert all('/content/t9b10/' not in x and '/content/t9b10.log' not in x for x in (worker,controller,L.read_text(),P.read_text()))
print(json.dumps({'archive_sha256':sha(arc),'members':len(manifest['members']),'stage_config':'31000 -> 2000, purge_avg 20000 -> 1000','protocol':'probe ready -> local bytes/sidecar sha verified','scope':'local protocol and archive dry run; NOT GPU physics','passed':True},ensure_ascii=False))
