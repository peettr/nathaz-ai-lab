"""Read-only salvage of complete 2015--2021 cohort after source time-axis audit."""
import json
from pathlib import Path
import numpy as np
r=Path('/content/l2612');src=json.loads((r/'manifest.json').read_text())['records']
by={}
for x in src:
 if x['year']>2021:continue
 if x['sid'] not in by or (x['wind_kt'],x['time'])>(by[x['sid']]['wind_kt'],by[x['sid']]['time']):by[x['sid']]=x
cohort=sorted(by.values(),key=lambda x:(x['year']>=2021,x['sid']))
assert len(cohort)==321 and sum(x['year']>=2021 for x in cohort)==46
windows=sorted((r/'windows').glob('*.npz'))
assert len(windows)==321 and [p.name for p in windows]==[f'{i:04d}.npz' for i in range(321)]
for i,p in enumerate(windows):
 with np.load(p) as a:assert a['window'].shape[1]==384 and len(a['indices'])==len(a['window']), (i,p)
(r/'cohort_2021.json').write_text(json.dumps(cohort,indent=1))
(r/'source_axis_audit.json').write_text(json.dumps({'era5_named_year_end':2022,'era5_actual_last':'2021-12-31T18:00','test_2021_storms':46,'test_2022_unavailable_storms':41,'salvaged_windows':321,'excluded_year':2022,'rule':'no nearest-time substitute; complete 2021 cohort used; 2022 in original manifest retained as unmet availability'},indent=1))
(r/'extract_2021.done').write_text('ok\n')
print('salvaged',len(cohort),'test',46,flush=True)
