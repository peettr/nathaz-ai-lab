import os,signal,pathlib,subprocess,time
pid=17925
cmd=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
assert cmd.strip()=='/content/l264a100/venv/bin/python /content/l264_west_forecasts.py',cmd
os.kill(pid,signal.SIGTERM);time.sleep(.5)
p=pathlib.Path('/content/l264a100/texas')
with (p/'west_batch_v2.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/l264_west_forecasts_v2.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('WEST_V2_PID',proc.pid,'old_pid_stopped',pid,flush=True)
