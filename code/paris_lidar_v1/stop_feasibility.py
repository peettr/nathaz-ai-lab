import os,subprocess
os.kill(3554,15)
print('stopped observation scan PID 3554 after feasibility gate')
print(subprocess.getoutput("ps -eo pid,args | grep '[r]un_observations.py'"))
