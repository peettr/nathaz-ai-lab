import pathlib,subprocess
p=pathlib.Path('/content/l264a100/texas');f=pathlib.Path('/content/l264a100/fast_data')
for n in ('texas_batch.log','west_batch_v2.log','air_batch.log','metric_batch.log','high_fetch.log'):
 q=p/n; print('LOG',n,q.read_text(errors='replace')[-1200:] if q.exists() else 'missing',flush=True)
for n in ('texas_forecast.done','west_forecast.done','texas_air.done','surface_metrics.done','air_metrics.done','metrics.done','high_fetch.done'):
 q=(f if n=='high_fetch.done' else p)/n;print('FLAG',n,q.exists(),flush=True)
print('PRED_COUNT',len(list((p/'predictions').glob('*.npz'))),flush=True)
