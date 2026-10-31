import subprocess,sys,pathlib
root=pathlib.Path('/content/site_stage_v2');root.mkdir(exist_ok=True)
log=(root/'admission.log').open('ab',buffering=0)
p=subprocess.Popen([sys.executable,'/content/station_admission_colab.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'admission.pid').write_text(str(p.pid));print('PID',p.pid)
