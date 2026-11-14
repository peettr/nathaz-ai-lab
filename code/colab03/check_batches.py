import pathlib,json,datetime,subprocess
p=pathlib.Path('/content/l264a100/texas');q=pathlib.Path('/content/l264a100/fast_data')
for name in ('texas_batch.log','west_batch.log'):
 f=p/name;print(name, f.read_text(errors='replace')[-1200:] if f.exists() else 'missing',flush=True)
for name in ('texas_forecast.done','west_forecast.done','metrics.done'):
 print(name,(p/name).exists(),flush=True)
f=q/'fast.log';print('FAST_LOG',f.read_text(errors='replace')[-350:] if f.exists() else 'missing','FAST_DONE',(q/'fast.done').exists(),flush=True)
if (q/'fast_increment.json').exists():print('FAST_MANIFEST',len(json.loads((q/'fast_increment.json').read_text())),flush=True)
print('SIZES',[(x.name,x.stat().st_size) for x in (p/'predictions').glob('*.npz')],flush=True)
