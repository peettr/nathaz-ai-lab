import pathlib,os,subprocess
for p in ['/content/l264a100/venv/bin/python','/content/l264texas01/venv/bin/python','/content/l264a100/texas/build_static.started','/content/l264_build_static.py','/content/l264a100/texas/table4_z0.json','/content/l264a100/fast_data/fast.done','/content/l264a100/fast_data/fast.log']:
 q=pathlib.Path(p);print(p,q.exists(),str(q.resolve()) if q.exists() else '',flush=True)
 if q.name=='fast.log' and q.exists():print('TAIL',q.read_text()[-400:],flush=True)
print('PS',subprocess.run(['ps','-eo','pid,etime,args'],capture_output=True,text=True).stdout[-3000:])
