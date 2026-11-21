import pathlib,json,os,hashlib
r=pathlib.Path('/content/t9b8');o=r/'out';ready={}
if o.exists():
 for side in sorted(o.glob('*.sha256')):
  p=side.with_name(side.name[:-7]);
  if p.is_file():ready[p.name]={'sha':side.read_text().strip(),'size':p.stat().st_size}
p=pathlib.Path('/content/t9b8.launch');pid=int(p.read_text()) if p.exists() else None
print('PROBE '+json.dumps({'pid':pid,'alive':bool(pid and pathlib.Path('/proc/'+str(pid)).exists()),'ready':ready,'done':(o/'run.done').exists(),'failed':(o/'run.failed').exists(),'log':pathlib.Path('/content/t9b8.log').read_text()[-500:] if pathlib.Path('/content/t9b8.log').exists() else ''}),flush=True)
