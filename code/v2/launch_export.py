import os,subprocess,pathlib,signal
try: os.kill(9445,signal.SIGTERM);print('stopped mistaken duplicate 9445',flush=True)
except ProcessLookupError:print('duplicate already exited',flush=True)
p=pathlib.Path('/content/l2613v2');assert (p/'OpenStreetMap_1.npy').exists()
with open('/content/l2613v2_export.log','x') as f:
 q=subprocess.Popen(['python','-u','/content/export_stl_corrected.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('export pid',q.pid,flush=True)
