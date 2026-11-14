import os,subprocess
for pid in (9561,9652):
 try: os.kill(pid,15);print('stopped',pid)
 except ProcessLookupError: pass
root='/content/zenodo19041698/attempt2';os.makedirs(root,exist_ok=True)
src=open('/content/zenodo19041698/download.py').read().replace('/content/zenodo19041698/','/content/zenodo19041698/attempt2/')
p=root+'/download.py';open(p,'w').write(src)
f=open(root+'/download.log','w');q=subprocess.Popen(['python',p],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('attempt2 PID',q.pid)
