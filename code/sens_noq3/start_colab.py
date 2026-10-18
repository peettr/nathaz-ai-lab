"""Launch the frozen-order no-Q3 sensitivity in a single CPU Colab session."""
import tarfile,pathlib,subprocess,sys,json,datetime
r=pathlib.Path('/content')
with tarfile.open(r/'noq3_bundle.tar') as t:t.extractall(r,filter='data')
p=r/'sens2'; p.mkdir(exist_ok=True)
assert not (p/'start.json').exists()
(p/'start.json').write_text(json.dumps({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
script='''import sys,subprocess,pathlib,json,datetime,traceback
p=pathlib.Path('/content/sens2')
try:
 for name in ('qc_noq3_colab.py','merge_colab.py','score_sens_colab_final.py','gev_sens_colab_final.py','derive_colab.py'):
  z=subprocess.run([sys.executable,str(p/name)],cwd='/content',check=True)
  print('STEP_DONE',name,flush=True)
  if name=='qc_noq3_colab.py':
   d=json.loads((p/'qc.done').read_text());assert d['errors']==0 and d['rows']==36,d
  if name=='merge_colab.py':assert sum(1 for _ in open('/content/sens4/qc_station_seasons.jsonl'))==435
 (p/'pipeline.exit.json').write_text(json.dumps({'returncode':0,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
except Exception as ex:
 traceback.print_exc()
 (p/'pipeline.exit.json').write_text(json.dumps({'returncode':1,'error':repr(ex),'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 sys.exit(1)
'''
(p/'pipeline.py').write_text(script)
f=(p/'pipeline.log').open('x')
proc=subprocess.Popen([sys.executable,str(p/'pipeline.py')],cwd='/content',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(p/'pid.json').write_text(json.dumps({'pid':proc.pid}))
print('STARTED',proc.pid)
