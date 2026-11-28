import subprocess
print(subprocess.run(['ps','-eo','pid,etime,args'],capture_output=True,text=True).stdout[-4000:])
