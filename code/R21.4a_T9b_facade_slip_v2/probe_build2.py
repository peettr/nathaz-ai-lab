import pathlib,json,hashlib
r=pathlib.Path('/content/t9b2/out')
ready={}
for p in r.glob('*.sha256'):
 f=r/p.name[:-7]
 if f.is_file():ready[p.name]={'sha':p.read_text().strip(),'size':f.stat().st_size}
print('PROBE',json.dumps({'ready':ready,'done':(r/'run.done').exists(),'failed':(r/'run.failed').exists(),'log':pathlib.Path('/content/t9b2.log').read_text()[-900:] if pathlib.Path('/content/t9b2.log').exists() else ''}))
