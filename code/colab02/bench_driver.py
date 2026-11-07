"""Three 48-frame training timings for each network, after inference."""
import os,pathlib,subprocess,time,json,traceback,statistics
p=pathlib.Path('/content/l264a100'); out=p/'bench';out.mkdir(exist_ok=False)
try:
 assert p.joinpath('full.done').exists(), 'full inference has not passed'
 results=[]
 for i in range(3):
  target=out/f'trial_{i+1}.json'; env=os.environ.copy();env.update(BENCH_OUTPUT=str(target),BENCH_FRAMES='48',CUDA_VISIBLE_DEVICES='0',PYTHONUNBUFFERED='1')
  t=time.monotonic()
  with (out/f'trial_{i+1}.log').open('w') as f:rc=subprocess.run([str(p/'venv/bin/python'),'/content/bench_finetune_l264.py'],stdout=f,stderr=subprocess.STDOUT,env=env,cwd=str(p/'AERO_ODE')).returncode
  print('TRIAL',i+1,'rc',rc,'wall_s',time.monotonic()-t,flush=True)
  assert rc==0 and target.is_file(),(out/f'trial_{i+1}.log').read_text()[-3000:]
  data=json.loads(target.read_text()); assert {r['network'] for r in data}=={'AIR','Surface'}
  results.extend(data)
  with (p/'bench_increment.jsonl').open('a') as f:f.write(json.dumps({'trial':i+1,'measurements':data})+'\n')
 summary={name:{'seconds':list(r['seconds_fwd_bwd_optimizer'] for r in results if r['network']==name),'median_seconds':statistics.median(r['seconds_fwd_bwd_optimizer'] for r in results if r['network']==name)} for name in ('AIR','Surface')}
 (p/'bench.done').write_text(json.dumps(summary,indent=2))
except BaseException:
 (p/'bench.failed').write_text(traceback.format_exc());traceback.print_exc();raise
