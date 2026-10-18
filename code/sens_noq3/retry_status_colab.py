from pathlib import Path
p=Path('/content/sens_retry');d=Path('/content/sens4')
print('EXIT', (p/'pipeline.exit.json').read_text() if (p/'pipeline.exit.json').exists() else 'running')
print('QC', (p/'qc.done').read_text() if (p/'qc.done').exists() else 'running')
print('RETRY_ROWS',sum(1 for _ in (p/'qc_station_seasons.jsonl').open()) if (p/'qc_station_seasons.jsonl').exists() else 0)
for x in ('merge_provenance.json','decision.json','gev_counts.json','changed_seasons.json'):
 f=d/x;print(x,f.read_text()[:1600] if f.exists() else 'pending')
f=p/'pipeline.log';print('LOG_END',f.read_text(errors='replace')[-2000:] if f.exists() else 'pending')
