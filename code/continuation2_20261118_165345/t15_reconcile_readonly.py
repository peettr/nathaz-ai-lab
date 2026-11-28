import pathlib, subprocess, json, time
p=pathlib.Path('/content/t15')
for n in ('/content/t15.log','/content/t15/out/run.done','/content/t15/out/run.failed'):
 q=pathlib.Path(n); print('FILE',n,q.exists(),q.stat().st_size if q.exists() else '',flush=True)
 if q.exists() and q.suffix in ('.done','.failed'):print('MARKER',q.read_text()[:1000],flush=True)
 if q.exists() and q.name=='t15.log':print('LOGTAIL', '\n'.join(q.read_text(errors='replace').splitlines()[-30:]),flush=True)
print('ACKS',[(q.name,q.read_text()[:200]) for q in (p/'out').glob('*.ack.json')],flush=True)
print('PROCS',subprocess.run(['ps','-eo','pid,etimes,args'],capture_output=True,text=True).stdout[-5000:],flush=True)
