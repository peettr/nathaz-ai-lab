import json
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parent
src=json.loads((R/'metrics_h3.json').read_text());screen=pd.read_csv(R/'screen_corrected_h3.csv').set_index('event')
for e in src['metadata']['events']:
 src['metadata']['counts'][e]['ts_cb_reports_corrected']=int(screen.loc[e,'n'])
src['metadata']['strict_no_ts_cb']=[e for e in src['metadata']['events'] if screen.loc[e,'n']==0]
src['metadata']['ts_cb_erratum']='Earlier regex counted TSNO (thunderstorm data not available) as thunderstorm; corrected regex TS(?!NO). Original metrics_h3.json/results_h3.md are preliminary, superseded, not overwritten.'
assert len(src['metadata']['strict_no_ts_cb'])==5
src['metrics']['COMBINED_STRICT']=src['metrics']['COMBINED_EXPLORATORY']
(R/'metrics_h3_corrected.json').open('x').write(json.dumps(src,ensure_ascii=False,indent=2))
print('strict',src['metadata']['strict_no_ts_cb'],'gain',src['metrics']['COMBINED_STRICT']['gain'])
