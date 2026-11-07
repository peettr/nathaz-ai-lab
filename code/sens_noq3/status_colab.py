from pathlib import Path
import json
p=Path('/content/sens2');q=Path('/content/sens4')
print('EXIT', (p/'pipeline.exit.json').read_text() if (p/'pipeline.exit.json').exists() else 'running')
print('QC_DONE', (p/'qc.done').read_text() if (p/'qc.done').exists() else 'pending')
for f in ('qc_station_seasons.jsonl','pipeline.log','new_isd_requests.json'):
 x=p/f;print(f,x.stat().st_size if x.exists() else 'missing')
for f in ('changed_seasons.json','decision.json','gev_counts.json'):
 x=q/f;print(f,x.read_text()[:1000] if x.exists() else 'missing')
if (p/'pipeline.log').exists():print('LOG_END', (p/'pipeline.log').read_text(errors='replace')[-3000:])
