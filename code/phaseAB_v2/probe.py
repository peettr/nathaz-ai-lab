import pathlib,json,hashlib
r=pathlib.Path('/content/phaseab_out')
print('PROBE',json.dumps({'ready':{p.name:{'sha':p.read_text().strip(),'size':(r/p.name.replace('_thin.sha256','_thin.npz')).stat().st_size} for p in r.glob('*_thin.sha256')},'ack':[p.name for p in r.glob('*.ack')],'done':(r/'run.done').exists(),'failed':(r/'run.failed').exists(),'stopped_A':(r/'run.stopped_A').exists(),'log':pathlib.Path('/content/phaseab.log').read_text()[-900:] if pathlib.Path('/content/phaseab.log').exists() else ''}))
