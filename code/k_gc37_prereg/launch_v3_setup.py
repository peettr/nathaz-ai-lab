import subprocess
p=subprocess.Popen(['python3','/content/setup_gc37_vm.py'],stdout=open('/content/setup_gc37_v3.log','x'),stderr=subprocess.STDOUT,start_new_session=True)
print('SETUP_PID',p.pid)
