import json
from pathlib import Path
p=Path('/content/site_stage_v2/station_only_seasons_corrected.jsonl');z=[json.loads(s) for s in p.read_text().splitlines()]
for st in ('KABR','KCRW'):
 a=sorted([x for x in z if x['station']==st],key=lambda x:x['peak']['kn'] if x['peak'] else -1,reverse=True)
 print(st,[(x['season_year'],x['peak']['kn'],x['peak']['event_utc'],x['peak']['source']) for x in a[:7]])
