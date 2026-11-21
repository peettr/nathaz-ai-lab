import pathlib,subprocess
p=pathlib.Path('/content/l2613v2');p.mkdir(exist_ok=True)
with open('/content/l2613v2_finish.log','w') as f:
 q=subprocess.Popen(['python','-u','/content/finish_v2.py'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
print('pid',q.pid)
