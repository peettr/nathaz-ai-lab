import os,subprocess
n=os.environ['MASS_GROUP'];assert n in ('D','M1','M2')
with open('/content/mass_'+n+'_wrapper.log','w') as f:
 p=subprocess.Popen(['python3','/content/remote_mass.py'],env=os.environ.copy(),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(n,p.pid)
