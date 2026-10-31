"""VM-only bounded Texas AIR zero-shot 10 daily 00Z; immutable forecasts."""
import pathlib,subprocess,time,json,datetime,os
P=pathlib.Path('/content/l264a100');T=P/'texas';F=P/'fast_data/fast_increment.json';PY=P/'venv/bin/python';SCRIPT=pathlib.Path('/content/l264_forecast_v2.py')
STOP=datetime.datetime(2026,10,22,19,15,tzinfo=datetime.timezone.utc).timestamp()
while not (T/'west_forecast.done').exists():
 if time.time()>STOP:raise RuntimeError('CU guard waiting west')
 time.sleep(15)
for day in range(1,11):
 target=f'data/era5_test/2024/04/{day:02d}/202404{day:02d}.nc'
 while target not in {v['path'] for v in json.loads(F.read_text())}:
  if time.time()>STOP:raise RuntimeError('CU guard before stage')
  time.sleep(15)
 if time.time()>STOP:raise RuntimeError('CU guard before AIR')
 print('AIR_START',day,datetime.datetime.now(datetime.timezone.utc),flush=True)
 subprocess.run([str(PY),str(SCRIPT),'--net','air','--region','texas','--variant','texas','--days',str(day)],check=True,stdin=subprocess.DEVNULL,env={**os.environ,'MPLBACKEND':'Agg'})
 print('AIR_DONE',day,datetime.datetime.now(datetime.timezone.utc),flush=True)
(T/'texas_air.done').write_text('10 air forecasts\n')
