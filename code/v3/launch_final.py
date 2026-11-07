import pathlib,subprocess
p=pathlib.Path('/content/l2613v3');assert (p/'generation.done').exists();assert all((p/x).exists() for x in ('final_worker.py','downstream_v3.py','export_stl_v3.py','official_roofs_reference.csv','RS_caseE.csv'))
f=(p/'final.log').open('xb');r=subprocess.Popen(['python',str(p/'final_worker.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('final PID',r.pid,flush=True)
