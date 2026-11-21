"""On-Colab bounded sequential run; never rerun a completed output."""
import runpy,sys,time,os,traceback,json
items=[(m,e,l) for m in ('Pangu6','FuXi') for e in ('E1','E2') for l in (12,24,48,72,120)]
start=time.monotonic(); base='/content/ai_weather'
for m,e,l in items:
    marker=f'{base}/{m}_{e}_{l}_grid25.json'
    if os.path.exists(marker):
        print('SKIP_EXISTING',m,e,l,flush=True);continue
    try:
        sys.argv=['/content/ai_weather_forecast.py',m,e,str(l)]
        runpy.run_path(sys.argv[0],run_name='__main__')
    except Exception:
        print('FAIL',m,e,l,traceback.format_exc(),flush=True)
        with open(f'{base}/fail_{m}_{e}_{l}.txt','w') as f:f.write(traceback.format_exc())
    print('ELAPSED',round(time.monotonic()-start,1),flush=True)
print('BATCH_DONE',round(time.monotonic()-start,1),flush=True)
