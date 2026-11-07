"""Resume only uncompleted forecast stages after path-only correction."""
import pathlib,subprocess,time,traceback
P=pathlib.Path('/content/l264ctrl05');py=P/'venv/bin/python'; start=time.monotonic()
def run(label,args):
 with (P/(label+'_v2.log')).open('x') as log:q=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 if q.returncode:raise RuntimeError(f'{label} rc={q.returncode}; see {label}_v2.log')
 print('DONE',label,'elapsed',round(time.monotonic()-start,2),flush=True)
try:
 assert (P/'stage.done').exists() and (P/'texas/build_static.done').exists()
 for net in ('air','surface'):
  for variant in ('original','shift0','shift10','shift50','shift150'):
   run(net+'_'+variant,[str(py),'/content/colab05_ctrl_forecast_v2.py','--net',net,'--region','shift','--variant',variant,'--days','1'])
 run('compare',[str(py),'/content/colab05_ctrl_compare.py'])
 (P/'ctrl.done').write_text('ok\n')
except BaseException:
 (P/'ctrl_v2.failed').write_text(traceback.format_exc());traceback.print_exc();raise
