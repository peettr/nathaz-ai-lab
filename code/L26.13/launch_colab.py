import subprocess
p=subprocess.Popen(['python','/content/run_colab.py'],stdin=subprocess.DEVNULL,stdout=open('/content/l2613_run.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('child_pid',p.pid)
