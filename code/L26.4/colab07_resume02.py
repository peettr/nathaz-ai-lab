"""Resume after XLA autotuner redzone abort without touching old logs/results."""
import pathlib,subprocess,sys,os,time,json,traceback
P=pathlib.Path('/content/l264surface07');root=P/'AERO_ODE';py=str(P/'venv/bin/python')
assert (P/'stage.done').exists() and (P/'install_py310.done').exists()
try:
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0',QUICK_MAX_BATCHES='1',QUICK_RESULT_DIR=str(P/'pilot02_result'),MPLBACKEND='Agg',PYTHONUNBUFFERED='1')
 begin=time.monotonic()
 with (P/'pilot02.log').open('x') as log:r=subprocess.run([py,str(root/'AERO_Surface_WD/test_film_00z_RMSE.py')],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 sec=time.monotonic()-begin
 print('PILOT02',r.returncode,round(sec,2),flush=True)
 text=(P/'pilot02.log').read_text()
 if r.returncode or 'Init: 2024/04/11/00' not in text or 'Evaluation Complete' not in text:raise RuntimeError('pilot02 failed '+text[-700:])
 (P/'pilot02.json').write_text(json.dumps({'pilot_s':sec,'start_init':'2024/04/11/00','gpu':'A100'}))
 print('PILOT02_BUDGET_GATE',flush=True)
 while not (P/'budget_go').exists():
  if (P/'budget_stop').exists():raise RuntimeError('budget stop')
  time.sleep(10)
 env['QUICK_MAX_BATCHES']='17';env['QUICK_RESULT_DIR']=str(P/'surface_result')
 begin=time.monotonic()
 with (P/'surface.log').open('x') as log:r=subprocess.run([py,str(root/'AERO_Surface_WD/test_film_00z_RMSE.py')],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 sec=time.monotonic()-begin
 print('SURFACE',r.returncode,round(sec,2),flush=True)
 text=(P/'surface.log').read_text()
 if r.returncode or 'Evaluation Complete [00Z Only, Surface Variables] (17 batches' not in text:raise RuntimeError('Surface incomplete '+text[-900:])
 (P/'surface_meta.json').write_text(json.dumps({'full_seconds':sec,'sample_count':17}))
 (P/'run.done').write_text('ok\n')
except BaseException:
 (P/'second_resume.failed').write_text(traceback.format_exc());traceback.print_exc();raise
