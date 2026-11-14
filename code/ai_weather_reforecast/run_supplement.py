"""Bounded supplement run on Colab; preserve every completed regional field."""
import os,sys,time,subprocess,traceback,json
from pathlib import Path
root=Path('/content/ai_weather');root.mkdir(exist_ok=True)
start=time.monotonic(); ledger=[]
try:
 for m in ('Pangu6','FuXi'):
  for e in ('E1','E2','E3'):
   for h in (12,24,48,72,120):
    suffix='supp_rhproxy' if m=='FuXi' else 'supp'
    mark=root/f'{m}_{e}_{h}_{suffix}.json'
    if mark.exists(): print('SKIP',m,e,h,flush=True);continue
    t=time.monotonic()
    cmd=[sys.executable,'/content/ai_weather_forecast_supp.py',m,e,str(h)]
    with (root/f'supp_{m}_{e}_{h}.log').open('w') as out:
     proc=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,timeout=600)
    record=dict(model=m,event=e,lead_h=h,exit_code=proc.returncode,seconds=round(time.monotonic()-t,1),marker=mark.exists())
    ledger.append(record)
    (root/'supp_progress.json').write_text(json.dumps(ledger,indent=2))
    print('STEP',record,'elapsed_s',round(time.monotonic()-start),flush=True)
    if proc.returncode or not mark.exists():raise RuntimeError(f'forecast failed: {record}')
 print('FORECASTS_COMPLETE',len(ledger),round(time.monotonic()-start),flush=True)
 (root/'supp_exit.txt').write_text('0')
except BaseException:
 (root/'supp_exit.txt').write_text(traceback.format_exc())
 traceback.print_exc()
 raise
