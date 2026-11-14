import os,signal,pathlib
pid=16003
cmd=pathlib.Path(f'/proc/{pid}/cmdline')
if cmd.exists():
 args=cmd.read_bytes().replace(b'\0',b' ').decode(errors='replace')
 print('PID_CMD',args)
 if '/content/l264_forecast.py' in args and '--region texas' in args:os.kill(pid,signal.SIGTERM);print('TERMINATED_OBSOLETE_PILOT',pid)
 else:raise RuntimeError('unexpected PID, no signal')
else:print('PID_ALREADY_EXITED',pid)
