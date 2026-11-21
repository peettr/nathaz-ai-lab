import subprocess
with open('/content/l2613v2_ground0.log','x') as f:
 p=subprocess.Popen(['python','-u','/content/export_stl_ground0.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('pid',p.pid)
