import os,subprocess
print(subprocess.run(['ps','aux'],capture_output=True,text=True).stdout[-3000:]);print(open('/content/e2/parallel.log').read()[-2000:])
