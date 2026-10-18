import subprocess
for tag in ('E1G0A35','E1G0A70'):
    with open('/content/'+tag+'.launch','w') as f:
        p=subprocess.Popen(['python3','/content/remote_keep2.py',tag],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    print(tag,p.pid)
