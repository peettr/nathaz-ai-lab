import pathlib,subprocess,time,datetime,os
P=pathlib.Path('/content/l264a100');T=P/'texas';PY=P/'venv/bin/python'
STOP=datetime.datetime(2026,10,22,19,19,tzinfo=datetime.timezone.utc).timestamp()
for name in ('texas_forecast.done','west_forecast.done','texas_air.done','high_fetch.done'):
 while not (T/name).exists():
  if time.time()>STOP:raise RuntimeError('CU guard waiting '+name)
  time.sleep(10)
 print('READY',name,flush=True)
for script in ('/content/l264_metrics_surface.py','/content/l264_metrics_high.py'):
 if time.time()>STOP:raise RuntimeError('CU guard metrics')
 print('METRICS_START',script,flush=True)
 subprocess.run([str(PY),script],check=True,stdin=subprocess.DEVNULL,env={**os.environ,'MPLBACKEND':'Agg'})
 print('METRICS_FINISHED',script,flush=True)
(T/'metrics.done').write_text('all three metric files and plot completed\n')
