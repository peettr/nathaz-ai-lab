import pathlib,subprocess,sys
p=pathlib.Path('/content/s1_corrected_ab.launch');p.open('x').write('start')
log=open('/content/s1_corrected_ab.log','x')
x=subprocess.Popen([sys.executable,'/content/s1_ab_corrected_1016.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',x.pid,flush=True)
