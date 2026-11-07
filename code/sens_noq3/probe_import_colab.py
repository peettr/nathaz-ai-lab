import sys,subprocess
print('KERNEL',sys.executable)
print('SUBPROCESS',subprocess.run([sys.executable,'-c','import lmoments3;print(lmoments3.__file__)'],capture_output=True,text=True).stdout)
print('USR_BIN',subprocess.run(['/usr/bin/python3','-c','import lmoments3;print(lmoments3.__file__)'],capture_output=True,text=True).stdout)
