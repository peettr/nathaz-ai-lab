import pathlib,subprocess
p=pathlib.Path('/content/l2613v3');assert(p/'extend_coverage.py').exists()
f=(p/'extend.log').open('xb');r=subprocess.Popen(['python',str(p/'extend_coverage.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('extend PID',r.pid,flush=True)
