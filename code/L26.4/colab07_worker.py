"""Colab VM sequential stage/install/one pilot, then explicit budget gate."""
import pathlib,subprocess,sys,os,time,json,traceback
P=pathlib.Path('/content/l264surface07');P.mkdir(exist_ok=True)
def run(label,command,env=None):
 start=time.monotonic()
 with (P/f'{label}.log').open('w') as f:
  r=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
 elapsed=time.monotonic()-start
 print(label,r.returncode,elapsed,flush=True)
 if r.returncode:raise RuntimeError(label+' failed '+str(r.returncode)+' '+(P/f'{label}.log').read_text()[-1200:])
 return elapsed
try:
 stage=run('stage',[sys.executable,'/content/l264stage07.py'])
 original=pathlib.Path('/content/l264install_base07.py').read_text()
 adapted=original.replace('/content/l264a100','/content/l264surface07')
 (P/'install_adapted.py').write_text(adapted)
 install=run('install',[sys.executable,str(P/'install_adapted.py')])
 root=P/'AERO_ODE';py=str(P/'venv/bin/python')
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0',QUICK_MAX_BATCHES='1',QUICK_RESULT_DIR=str(P/'pilot_result'),MPLBACKEND='Agg',PYTHONUNBUFFERED='1')
 pilot=run('pilot',[py,str(root/'AERO_Surface_WD/test_film_00z_RMSE.py')],env)
 text=(P/'pilot.log').read_text()
 if 'Init: 2024/04/11/00' not in text or 'Evaluation Complete' not in text:raise RuntimeError('wrong pilot init or incomplete')
 (P/'pilot.json').write_text(json.dumps({'stage_s':stage,'install_s':install,'pilot_s':pilot,'start_init':'2024/04/11/00','gpu':'A100'}))
 print('PILOT_COMPLETE_BUDGET_GATE',pilot,flush=True)
 while not (P/'budget_go').exists():
  if (P/'budget_stop').exists():raise RuntimeError('budget stop')
  time.sleep(10)
 env['QUICK_MAX_BATCHES']='17';env['QUICK_RESULT_DIR']=str(P/'surface_result')
 full=run('surface',[py,str(root/'AERO_Surface_WD/test_film_00z_RMSE.py')],env)
 text=(P/'surface.log').read_text()
 if 'Evaluation Complete [00Z Only, Surface Variables] (17 batches' not in text:raise RuntimeError('not 17 completed')
 (P/'surface_meta.json').write_text(json.dumps({'full_seconds':full,'sample_count':17}))
 (P/'run.done').write_text('ok\n')
except BaseException:
 (P/'run.failed').write_text(traceback.format_exc());traceback.print_exc();raise
