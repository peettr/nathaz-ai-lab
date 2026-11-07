import os, subprocess
print(subprocess.run(['ps','-eo','pid,ppid,etime,args'],capture_output=True,text=True).stdout[-5000:])
for f in ('/content/rmw_test.log','/content/rmw_test.exit','/content/rmw_test.done'):
 print(f,os.path.exists(f))
 if os.path.isfile(f):print(open(f).read()[-4000:])
