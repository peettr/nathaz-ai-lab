import pathlib,json,os
p=pathlib.Path('/content/s0_pair_1016.log');print('LOG',p.read_text()[-3500:] if p.exists() else 'MISSING');q=pathlib.Path('/content/s0_pair_1016.pid');print('PID',q.read_text() if q.exists() else None);print('PROC',os.path.exists('/proc/'+q.read_text()) if q.exists() else None)
c=pathlib.Path('/content/s0_pair_1016/progress.json');print('CHECKPOINT',c.read_text()[-500:] if c.exists() else None)
print('DONE',pathlib.Path('/content/s0_pair_1016/DONE').read_text() if pathlib.Path('/content/s0_pair_1016/DONE').exists() else None)
print('METAR_FILES',len(list(pathlib.Path('/content/s0_pair_1016').glob('metar_*.json'))))
if q.exists():print('PROC_STATUS',pathlib.Path('/proc/'+q.read_text()+'/status').read_text()[:700])
