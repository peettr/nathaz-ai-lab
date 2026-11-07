import shutil,pathlib
p=pathlib.Path('/content/l264a100/texas');print('DISK',shutil.disk_usage('/content'))
for n in ('air_batch_v3.log','metric_batch_v3.log'):
 f=p/n;print(n,f.read_text(errors='replace')[-700:])
print('PRED',[(f.name,f.stat().st_size) for f in (p/'predictions').glob('texas_texas_air_*.npz')])
