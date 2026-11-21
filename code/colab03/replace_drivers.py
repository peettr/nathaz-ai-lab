import pathlib,os,signal,subprocess,time
p=pathlib.Path('/content/l264a100/texas')
for pid,name in ((20216,'l264_air_forecasts.py'),(22673,'l264_run_metrics.py')):
 cmd=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
 assert cmd.strip()==f'/content/l264a100/venv/bin/python /content/{name}',cmd
 os.kill(pid,signal.SIGTERM)
time.sleep(.3)
for filename,logname in (('l264_west_forecasts_v3.py','west_batch_v3.log'),('l264_air_forecasts_v3.py','air_batch_v3.log'),('l264_run_metrics_v3.py','metric_batch_v3.log')):
 with (p/logname).open('x') as log:
  proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/'+filename],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'MPLBACKEND':'Agg'})
 print(filename,'PID',proc.pid,flush=True)
