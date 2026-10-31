import subprocess,pathlib
r=subprocess.run(['ps','-eo','pid,ppid,args'],capture_output=True,text=True,check=True)
for line in r.stdout.splitlines():
 if any(s in line for s in ('l264_west_forecasts.py','l264_texas_forecasts.py','l264_air_forecasts.py','l264_fetch_high.py')):print(line,flush=True)
p=pathlib.Path('/content/l264a100/texas')
for n in ('high_fetch.log','west_batch.log','air_batch.log'):
 f=p/n;print(n,f.read_text(errors='replace')[-800:] if f.exists() else 'missing',flush=True)
