import pathlib,json
r=pathlib.Path('/content/t5_out')
print('PROBE',json.dumps({'ready':{p.name:{'sha':p.read_text().strip(),'size':(r/p.name.replace('.sha256','')).stat().st_size} for p in r.glob('*.sha256')},'ack':[p.name for p in r.glob('*.ack')],'done':(r/'run.done').exists(),'failed':(r/'run.failed').exists(),'log':pathlib.Path('/content/t5.log').read_text()[-800:] if pathlib.Path('/content/t5.log').exists() else ''}))
