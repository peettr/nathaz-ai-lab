from pathlib import Path
import hashlib, json, shutil, tarfile
R=Path(__file__).resolve().parent; P=R.parent; B=P/'build12_20261117_145427'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(name,s):
 with (R/name).open('x') as f:f.write(s)
def replace(s,a,b):
 assert s.count(a)==1,a
 return s.replace(a,b)
for base, names in [(B,['t9b12_source.tar.gz','t9b12_manifest.json','LOCAL_PREFLIGHT.json']),(P,['t9b2_stage.tar.gz','t9b2_archive.json'])]:
 for n in names:
  with (R/n).open('xb') as f:f.write((base/n).read_bytes())
for src,n in [(P.parent/'R21.4a_T5_caseE_WM_retry1/worker.py','t5_reference_worker.py'),(P.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py','remote_worker_run2.py')]:put(n,src.read_text())
s=(B/'worker_gate.py').read_text().replace('/content/t9b12','/content/t9b14')
s=replace(s,'T9b build12: frozen v9 channel and cube A; conditional city B.','T9b build14: frozen v11 y-channel and cube A; conditional city B.')
s=replace(s,"for wall in ('x','y'):","for wall in ('y',):")
s=replace(s,"drift=abs(end-m0)/m0;ratio=end/m0\n   ok=(drift<=1e-5 if state=='on' else ratio<=0.9)","drift=(end-m0)/m0;ratio=end/m0\n   series=[(float(row['tangent_momentum'])-m0)/m0 for row in rows]\n   ok=(-1e-5<=min(series) and max(series)<=1e-4 if state=='on' else ratio<=0.9)")
s=replace(s,"'ratio':ratio,'trace_sha256'","'ratio':ratio,'min_relative':min(series),'max_relative':max(series),'trace_sha256'")
s=replace(s,"b['deadline']-300","b['deadline']-130")
s=replace(s,"plus 300 s","plus 130 s")
s=replace(s,"budget_guard(1700,","budget_guard(2930,")
s=replace(s,"budget_guard(1350,","budget_guard(2800,")
s=replace(s,"budget_guard(420 if state=='off' else 220,","budget_guard(340 if state=='off' else 170,")
s=replace(s,"config.write_text(text);ready(config)","config.write_text(text)\n  staged=O/(f'city_2000_{state}_conf.luwpf');staged.write_text(text);ready(staged)")
s=replace(s,"differences=[p['id'] for p,q in zip(short['off'],short['on']) if p!=q]","assert [p['id'] for p in short['off']]==[p['id'] for p in short['on']]\n differences=[p['id'] for p,q in zip(short['off'],short['on']) if p['Su']!=q['Su']]")
s=replace(s,"'count':len(differences),","'count':len(differences),'max_abs_delta_Su':max(abs(p['Su']-q['Su']) for p,q in zip(short['off'],short['on'])),")
s=replace(s,"(O/'run.done').write_text", "ack=O/'host_ack.json'; expected={p.name[:-7]:p.read_text().strip() for p in O.glob('*.sha256')}\n while not ack.exists():\n  budget_guard(0,'final host ACK');time.sleep(2)\n assert json.loads(ack.read_text())==expected,'ACK mismatch'\n (O/'run.done').write_text")
s=replace(s,"with p.open('x') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=limit)","deadline=json.loads(pathlib.Path('/content/t9b14_budget.json').read_text())['deadline']\n  with p.open('x') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=max(1,min(limit,deadline-time.time()-150)))")
put('worker_gate.py',s)
s=(B/'launch_gate.py').read_text().replace('/content/t9b12','/content/t9b14')
s=s.replace("else:\n f=open", "else:\n import hashlib,json\n assert all(hashlib.sha256(pathlib.Path('/content',n).read_bytes()).hexdigest()==h for n,h in json.loads(pathlib.Path('/content/t9b14_upload.json').read_text()).items())\n f=open")
put('launch_gate.py',s)
s=(B/'probe_gate.py').read_text().replace('/content/t9b12','/content/t9b14').replace("'ready':ready,","'ready':ready,'b_passed':(o/'stage_B_verdict.json.sha256').exists(), 'ack':(o/'host_ack.json').exists(),")
s=s.replace("pathlib.Path('/content/t9b14.log').read_text()[-500:]","pathlib.Path('/content/t9b14.log').read_text(errors='replace')[-500:]")
put('probe_gate.py',s)
put('machine.py',"import subprocess\nsubprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],check=True)\nprint(next(x.strip() for x in open('/proc/meminfo') if x.startswith('MemAvailable:')))\n")
for pkg,manifest,root in [('t9b12_source.tar.gz','t9b12_manifest.json','FluidX3D_facade_v11'),('t9b2_stage.tar.gz','t9b2_archive.json','stage')]:
 m=json.loads((R/manifest).read_text());assert sha(R/pkg)==m['archive_sha256']
 if root.startswith('Fluid'):assert sha(R/pkg)=='13bc199a005cfdf99cb7e81de79382676fcc4c2479e6abcc35ff4ef9296be9aa'
 with tarfile.open(R/pkg) as t:
  assert all((x.name==root or x.name.startswith(root+'/')) and '..' not in Path(x.name).parts and (x.isfile() or x.isdir()) for x in t.getmembers())
  for n,h in m['members'].items():assert hashlib.sha256(t.extractfile(root+'/'+n).read()).hexdigest()==h,n
  if root=='stage':
   config=t.extractfile('stage/case/conf.luwpf').read().decode();assert config.count('run_nstep = 31000')==config.count('purge_avg = 20000')==1
   assert len(json.load(t.extractfile('stage/B2u_reference_points.json'))['rows'])==80
 print(pkg,len(m['members']),sha(R/pkg))
put('EXPERIMENT_CARD.md',f'''# R21.4a T9b-build14
1. 假设：立面镜面滑移在 y 墙抑制切向衰减，且不改城市关闭态复现和 flags。
2. 唯一对照变量 FACADE_FREE_SLIP；不改 v11 冻结源码；不重跑 x。A100；上位项目执行规则限制 G4。
3. 源包 t9b12_source.tar.gz SHA256 {sha(R/'t9b12_source.tar.gz')}；城市输入 t9b2_stage.tar.gz SHA256 {sha(R/'t9b2_stage.tar.gz')}。
4. 运行根 {R}；各尝试事件见 attempt_*/events.jsonl。
5. y 关末/初 ≤0.9；开全 0–1000 步 [−1e−5,+1e−4]（11-17 看完历史 x 数据后修订，本轮开跑前冻结）；开关 trace SHA 不同。立方体仅描述。A 过后比较 s101 冻结 SHA、原生 flags 与 2000 步 80 点 Su；5.5 CU 止损，6 CU 硬限。
''')
