import pathlib,subprocess,sys
c=pathlib.Path('/content');m=c/'t15_upper.launch'
if m.exists():print('UPPER_ALREADY',m.read_text(),flush=True)
else:
 with m.open('x') as f,(c/'t15_upper.log').open('x') as o:
  p=subprocess.Popen([sys.executable,str(c/'profile_upper_remote.py')],cwd=c,stdin=subprocess.DEVNULL,stdout=o,stderr=subprocess.STDOUT,start_new_session=True)
  f.write(str(p.pid))
  print('UPPER_LAUNCHED',p.pid,flush=True)
