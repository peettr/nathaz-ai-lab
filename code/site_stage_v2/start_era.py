import subprocess,sys,pathlib
root=pathlib.Path('/content/site_stage_v2');log=(root/'era.log').open('ab',buffering=0)
p=subprocess.Popen([sys.executable,'/content/era_v2_colab.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'era.pid').write_text(str(p.pid));print('ERA_PID',p.pid)
