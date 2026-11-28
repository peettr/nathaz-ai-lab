import subprocess
p=subprocess.Popen(['python3','/content/infer_gc37_v3.py'],stdout=open('/content/infer_gc37_v3_stdout.log','x'),stderr=subprocess.STDOUT,start_new_session=True)
print('V3_INFER_PID',p.pid)
