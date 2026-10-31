"""West static intervention 3 days, 2 variants, 2 frozen networks."""
import pathlib,subprocess,time,json,datetime,os
P=pathlib.Path('/content/l264a100');T=P/'texas';F=P/'fast_data/fast_increment.json';PY=P/'venv/bin/python';SCRIPT=pathlib.Path('/content/l264_forecast_v2.py')
STOP=datetime.datetime(2026,10,22,19,15,tzinfo=datetime.timezone.utc).timestamp()
while not (T/'texas_forecast.done').exists():
 if time.time()>STOP:raise RuntimeError('CU guard waiting texas')
 time.sleep(15)
for net in ('air','surface'):
 for variant in ('original','west'):
  for day in (1,2,3):
   target=f'data/hrrr_test/04/{day:02d}.h5'
   while target not in {v['path'] for v in json.loads(F.read_text())}:
    if time.time()>STOP:raise RuntimeError('CU guard waiting HRRR west')
    time.sleep(15)
   if time.time()>STOP:raise RuntimeError('CU guard before west forecast')
   print('WEST_START',net,variant,day,datetime.datetime.now(datetime.timezone.utc),flush=True)
   env={**os.environ,'MPLBACKEND':'Agg'}
   subprocess.run([str(PY),str(SCRIPT),'--net',net,'--region','west','--variant',variant,'--days',str(day)],check=True,stdin=subprocess.DEVNULL,env=env)
   print('WEST_DONE',net,variant,day,datetime.datetime.now(datetime.timezone.utc),flush=True)
(T/'west_forecast.done').write_text('12 contrasts done\n')
