import pathlib,subprocess,sys
p=pathlib.Path('/content/s1_corrected_c.launch');p.open('x').write('start')
log=open('/content/s1_c_corrected.log','x')
x=subprocess.Popen([sys.executable,'/content/s1_c_corrected_1016.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',x.pid,flush=True)
