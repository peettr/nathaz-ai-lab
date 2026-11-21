"""Run the unchanged author tests sequentially for exactly ten 00Z initializations."""
import os,pathlib,subprocess,time,json,traceback,hashlib
p=pathlib.Path('/content/l264a100');root=p/'AERO_ODE';out=p/'full';out.mkdir(exist_ok=False)
py=str(p/'venv/bin/python')
try:
 assert (p/'pilot.done').exists(), 'pilot CU gate not passed'
 for name,script,filename in [('air','AERO_AIR_WD/test_film_wb.py','rmse_aero_00z.npy'),('surface','AERO_Surface_WD/test_film_00z_RMSE.py','rmse_surface_00z_smoke10.npy')]:
  dest=out/name;dest.mkdir()
  env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0',QUICK_MAX_BATCHES='10',QUICK_RESULT_DIR=str(dest),MPLBACKEND='Agg',PYTHONUNBUFFERED='1')
  start=time.monotonic()
  with (out/(name+'.log')).open('w') as log:rc=subprocess.run([py,str(root/script)],env=env,cwd=str(root),stdout=log,stderr=subprocess.STDOUT).returncode
  body=(out/(name+'.log')).read_text(); elapsed=time.monotonic()-start
  print('FULL',name,'rc',rc,'seconds',elapsed,'tail',body[-1000:],flush=True)
  assert rc==0 and (dest/filename).is_file() and '(10 batches' in body and 'Evaluation Complete' in body,name+' failed: '+body[-3000:]
  increments=p/'full_increment.jsonl'
  with increments.open('a') as f:f.write(json.dumps({'network':name,'seconds':elapsed,'count':10,'npy':str(dest/filename),'log':str(out/(name+'.log'))})+'\n')
 (p/'full.done').write_text('ok\n')
except BaseException:
 (p/'full.failed').write_text(traceback.format_exc());traceback.print_exc();raise
