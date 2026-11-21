# Launch the staged split run on this Colab VM
import os,subprocess,sys
name=os.environ['LUW_TAG']
assert name in ('E1','E05','C1G0')
log=open('/content/launch_'+name+'.log','w')
p=subprocess.Popen(['python3','/content/remote_split.py',name],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(name,p.pid,flush=True)
