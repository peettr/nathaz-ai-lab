import subprocess,sys,pathlib
p=pathlib.Path('/content/s1_ab_full_v2.launch');p.open('x').write('start')
log=open('/content/s1_ab_full_v2.log','x')
x=subprocess.Popen([sys.executable,'/content/s1_ab_full_1016.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',x.pid)
