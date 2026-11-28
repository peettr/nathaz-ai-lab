import pathlib,subprocess
p=pathlib.Path('/content/l264ctrl05');assert (p/'ctrl.failed').exists()
with (p/'ctrl_resume.log').open('x') as f:
 x=subprocess.Popen(['python','/content/colab05_ctrl_resume.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('RESUME_PID',x.pid,flush=True)
