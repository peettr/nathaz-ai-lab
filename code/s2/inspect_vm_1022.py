import os, subprocess
for cmd in ['df -h / /content','ps -eo pid,stat,etime,args | grep -E "resume_inner_20_130|s2.*py" | grep -v grep','du -sh /content/s2 /root/.cache /tmp /content 2>/dev/null']:
    print('CMD',cmd)
    p=subprocess.run(cmd,shell=True,text=True,capture_output=True,timeout=30)
    print(p.stdout[-3000:],p.stderr[-500:])
print('DONE FILES', [x for x in os.listdir('/content/s2') if 'done' in x])
