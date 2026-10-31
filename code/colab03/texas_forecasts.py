"""VM-only bounded sequential Texas forecasts, preserving each existing result."""
import pathlib,subprocess,time,json,datetime,sys
P=pathlib.Path('/content/l264a100');T=P/'texas';F=P/'fast_data/fast_increment.json';PY=P/'venv/bin/python';SCRIPT=pathlib.Path('/content/l264_forecast_v2.py')
# 10-22 15:15 EDT; leave time to evaluate/pull and stop before 18 CU.
STOP=datetime.datetime(2026,10,22,19,15,tzinfo=datetime.timezone.utc).timestamp()
for day in range(2,11):
 target=f'data/era5_test/2024/04/{day:02d}/202404{day:02d}.nc'
 while target not in {v['path'] for v in json.loads(F.read_text())}:
  if time.time()>STOP:raise RuntimeError('CU guard before stage day '+str(day))
  time.sleep(10)
 if time.time()>STOP:raise RuntimeError('CU guard before forecast day '+str(day))
 print('START_DAY',day,'UTC',datetime.datetime.now(datetime.timezone.utc),flush=True)
 subprocess.run([str(PY),str(SCRIPT),'--net','surface','--region','texas','--variant','texas','--days',str(day)],check=True,stdin=subprocess.DEVNULL)
 print('COMPLETE_DAY',day,'UTC',datetime.datetime.now(datetime.timezone.utc),flush=True)
(T/'texas_forecast.done').write_text('10 days complete\n')
