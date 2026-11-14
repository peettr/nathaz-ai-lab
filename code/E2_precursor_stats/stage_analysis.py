import os,subprocess,time
p='/content/e2/download_meta.json'
script='/content/e2/analyze_e2.py'
f=open('/content/e2/analyze.log','w')
cmd='while [ ! -f /content/e2/download_meta.json ]; do sleep 2; done; python /content/e2/analyze_e2.py'
q=subprocess.Popen(['bash','-c',cmd],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('ANALYSIS_WATCHER_PID',q.pid)
