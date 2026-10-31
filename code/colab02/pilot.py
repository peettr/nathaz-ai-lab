"""One-initialization budget gate, no full run until inspected."""
import os, pathlib, subprocess, time, json, traceback, hashlib
p=pathlib.Path('/content/l264a100'); root=p/'AERO_ODE'; out=p/'pilot';out.mkdir(exist_ok=False)
py=str(p/'venv/bin/python')
expected={'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth':'5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb','AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth':'4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c','shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl':'43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7'}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
try:
 assert (p/'stage.done').is_file() and (p/'install_py310.done').is_file(),'stage/install incomplete'
 for rel,h in expected.items():
  got=sha(root/rel);print('WEIGHT',rel,got,flush=True);assert got==h,rel
 jobs=[('air','AERO_AIR_WD/test_film_wb.py','rmse_aero_00z.npy'),('surface','AERO_Surface_WD/test_film_00z_RMSE.py','rmse_surface_00z_smoke1.npy')]
 results={}
 for name,script,filename in jobs:
  runout=out/name;runout.mkdir()
  env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0', QUICK_MAX_BATCHES='1',QUICK_RESULT_DIR=str(runout),MPLBACKEND='Agg',PYTHONUNBUFFERED='1')
  start=time.monotonic()
  with (out/(name+'.log')).open('w') as log:rc=subprocess.run([py,str(root/script)],env=env,cwd=str(root),stdout=log,stderr=subprocess.STDOUT).returncode
  seconds=time.monotonic()-start
  tail=(out/(name+'.log')).read_text()[-3000:]
  print('PILOT',name,'rc',rc,'seconds',seconds,'result',str(runout/filename),'tail',tail[-500:],flush=True)
  assert rc==0 and (runout/filename).is_file() and 'Evaluation Complete' in (out/(name+'.log')).read_text(),name+' failed: '+tail
  results[name]={'seconds':seconds,'log':str(out/(name+'.log')),'npy':str(runout/filename)}
  (p/'pilot_increment.json').write_text(json.dumps(results,indent=2))
 (p/'pilot.done').write_text(json.dumps(results,indent=2))
except BaseException:
 (p/'pilot.failed').write_text(traceback.format_exc());traceback.print_exc();raise
