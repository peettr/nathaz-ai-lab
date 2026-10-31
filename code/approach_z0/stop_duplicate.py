import os,signal,subprocess
for pid in (1643,1697):
 try: print(pid,open(f'/proc/{pid}/cmdline','rb').read().replace(b'\0',b' '))
 except Exception as e: print(e)
try: os.kill(1697,signal.SIGTERM);print('stopped duplicate 1697')
except Exception as e:print(e)
print(subprocess.run(['pgrep','-af','remote_z0.py'],capture_output=True,text=True).stdout)
