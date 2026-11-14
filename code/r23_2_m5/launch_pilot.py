import os,subprocess
p='/content/m5/pilot.launch'
with open(p,'x') as f:f.write('m5 pilot\n')
a=subprocess.Popen(['bash','/content/m5/pilot.sh'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('PILOT_PID',a.pid)
