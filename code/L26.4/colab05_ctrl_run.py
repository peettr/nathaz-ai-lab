"""Bounded location/path control, on disposable Colab VM."""
import pathlib,subprocess,time,json,csv,traceback
P=pathlib.Path('/content/l264ctrl05'); T=P/'texas'; T.mkdir(exist_ok=True)
py=P/'venv/bin/python'; start=time.monotonic()
def run(label,args):
 with (P/(label+'.log')).open('x') as log:
  q=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 if q.returncode:raise RuntimeError(f'{label} rc={q.returncode}; log {P/(label+".log")}')
 print('DONE',label,'elapsed',round(time.monotonic()-start,2),flush=True)
try:
 while not (P/'stage.done').exists():
  if (P/'stage.failed').exists():raise RuntimeError((P/'stage.failed').read_text()[-3000:])
  time.sleep(10)
 lookup={}
 with open('/content/Table4_IGBP_z0.csv') as f:
  for row in csv.DictReader(line for line in f if not line.startswith('#')):lookup[row['igbp_class']]=float(row['z0_m'])
 (T/'table4_z0.json').write_text(json.dumps(lookup))
 run('static_probe',[str(py),'/content/colab05_ctrl_static_probe.py'])
 run('build_static',[str(py),'/content/colab05_ctrl_build_static.py'])
 # One frozen init; original and moved variants use independent processes to release GPU.
 for net in ('air','surface'):
  for variant in ('original','shift0','shift10','shift50','shift150'):
   run(f'{net}_{variant}',[str(py),'/content/colab05_ctrl_forecast.py','--net',net,'--region','shift','--variant',variant,'--days','1'])
 run('compare',[str(py),'/content/colab05_ctrl_compare.py'])
 (P/'ctrl.done').write_text('ok\n')
except BaseException:
 (P/'ctrl.failed').write_text(traceback.format_exc());traceback.print_exc();raise
