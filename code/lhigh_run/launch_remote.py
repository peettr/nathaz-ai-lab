import os,subprocess
kind=os.environ['TASK_KIND']; assert kind in ('D80','H1','H2')
script='/content/remote_d80.py' if kind=='D80' else '/content/remote_city_one.py'
env=os.environ.copy();env['CITY_GROUP']=kind if kind!='D80' else 'H1'
with open('/content/lhigh_'+kind+'_wrapper.log','w') as f:
 p=subprocess.Popen(['python3',script],cwd='/content',env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('launched',kind,p.pid,flush=True)
