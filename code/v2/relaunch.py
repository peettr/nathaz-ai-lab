import pathlib,subprocess
p=pathlib.Path('/content/l2613v2/run.done')
if p.exists():p.unlink()
subprocess.run(['cp','/content/run_v2_resume.py','/content/l2613v2/run_v2_resume.py'],check=True)
with open('/content/l2613v2_resume.log','w') as f:
 q=subprocess.Popen(['python','-u','/content/l2613v2/run_v2_resume.py'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
print('resume pid',q.pid)
