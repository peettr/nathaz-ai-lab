import os, json, pathlib, subprocess, time
root=pathlib.Path('/content/v6_work')
for name in ('sanity','group'):
 p=root/name
 if not p.exists(): continue
 pid=int((p/'pid').read_text())
 alive=pathlib.Path(f'/proc/{pid}').exists()
 print(name,'pid',pid,'alive',alive,'files',[x.name for x in p.iterdir() if x.name in ('FINISHED','FAILED','segment_summary.json')],flush=True)
 for f in ('HEARTBEAT.json','segment_summary.json'):
  if (p/f).exists(): print(f,(p/f).read_text()[:500],flush=True)
 if (p/'launcher.log').exists():
  lines=(p/'launcher.log').read_text().splitlines()
  print('log_tail','\n'.join(lines[-8:])[-1800:],flush=True)
