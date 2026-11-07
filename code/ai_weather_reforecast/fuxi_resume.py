"""Resume remaining FuXi forecasts after ARCO RH adapter smoke test."""
import runpy,sys,time,os,traceback
base='/content/ai_weather';t0=time.monotonic()
for e in ('E1','E2'):
 for l in (12,24,48,72,120):
  p=f'{base}/FuXi_{e}_{l}_grid25_rhproxy_v2.json'
  if os.path.exists(p):print('SKIP_EXISTING',e,l,flush=True);continue
  try:
   sys.argv=['/content/ai_weather_forecast.py','FuXi',e,str(l)]
   _=runpy.run_path(sys.argv[0],run_name='__main__')
  except Exception:
   print('FAIL',e,l,traceback.format_exc(),flush=True)
  print('ELAPSED',round(time.monotonic()-t0),flush=True)
print('FUXI_DONE',round(time.monotonic()-t0),flush=True)
