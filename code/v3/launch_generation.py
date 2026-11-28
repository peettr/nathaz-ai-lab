import pathlib,subprocess
p=pathlib.Path('/content/l2613v3');assert (p/'generate_v3.py').exists();assert(p/'coverage_adjacent.done').exists();f=(p/'generation.log').open('xb');r=subprocess.Popen(['python',str(p/'generate_v3.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('generation PID',r.pid,flush=True)
