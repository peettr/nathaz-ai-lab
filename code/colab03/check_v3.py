import pathlib,subprocess
p=pathlib.Path('/content/l264a100/texas')
for n in ('west_batch_v3.log','air_batch_v3.log','metric_batch_v3.log'):
 q=p/n;print(n,q.read_text(errors='replace')[-1800:] if q.exists() else 'missing',flush=True)
for n in ('west_forecast.done','texas_air.done','metrics.done','texas_air_metrics.json','west_intervention.json','texas_metrics.json'):
 q=p/n;print(n,q.exists(),q.stat().st_size if q.exists() else '-',flush=True)
