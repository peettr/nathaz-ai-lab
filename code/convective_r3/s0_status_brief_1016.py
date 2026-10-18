import pathlib,json,os
root=pathlib.Path('/content/s0_pair_1016');cp=root/'progress.json';log=pathlib.Path('/content/s0_pair_1016.log')
print('CHECKPOINT', {k:v for k,v in json.loads(cp.read_text()).items() if k not in ('paired','unpaired')} if cp.exists() else None)
print('DONE',(root/'DONE').read_text() if (root/'DONE').exists() else None)
print('LOG_TAIL','\n'.join(log.read_text().splitlines()[-6:]) if log.exists() else None)
q=pathlib.Path('/content/s0_pair_1016.pid');print('WORKER',q.read_text() if q.exists() else None, pathlib.Path('/proc/'+q.read_text()+'/status').read_text().splitlines()[2] if q.exists() and pathlib.Path('/proc/'+q.read_text()+'/status').exists() else 'MISSING')
