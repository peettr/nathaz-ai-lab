import pathlib,json,hashlib
r=pathlib.Path('/content/t8_out'); log=pathlib.Path('/content/t8.log')
print('PROBE',json.dumps({'ready':{p.name: {'sha':p.read_text().strip(),'size':(r/p.name[:-7]).stat().st_size} for p in r.glob('*.sha256') if (r/p.name[:-7]).is_file()},'ack':(r/'host.ack').exists(),'done':(r/'run.done').exists(),'failed':(r/'run.failed').exists(),'tail':log.read_text()[-650:] if log.exists() else ''}))
