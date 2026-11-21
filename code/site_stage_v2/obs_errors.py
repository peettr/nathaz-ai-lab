import json,collections
from pathlib import Path
p=Path('/content/site_stage_v2/station_only_seasons.jsonl');z=[json.loads(x) for x in p.read_text().splitlines()];e=[(x['station'],x['season_year'],x.get('error')) for x in z if x.get('error')];print('count',len(z),'errors',e,'invalid',[(x['station'],x['season_year'],x.get('coverage')) for x in z if not x.get('valid') and not x.get('error')]);print('done marker',Path('/content/site_stage_v2/admission.done').exists())
