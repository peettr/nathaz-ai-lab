"""Summarize frozen main and completed sensitivity outputs on Colab."""
import csv,json,numpy as np
from pathlib import Path
r=Path('/content/site_stage_v2');a=list(csv.DictReader((r/'loso_results.csv').open()));s=list(csv.DictReader((r/'sensitivity_results.csv').open()));g=list(csv.DictReader((r/'gev_lmom_sensitivity.csv').open()));d=list(csv.DictReader((r/'event_diagnostic.csv').open()));adm=list(csv.DictReader((r/'station_admission.csv').open()))
out={'admitted':{c:sum(x['admitted']=='true' and x['region']==c for x in adm) for c in ('plains','other')},'rejected':{c:[{'station':x['station'],'reasons':x['reasons']} for x in adm if x['admitted']=='false' and x['region']==c] for c in ('plains','other')},'main_extreme_R':[{'station':x['station'],'R10':float(x['R10']),'R50':float(x['R50'])} for x in a if abs(np.log(float(x['R10'])))>.4], 'sensitivity':{},'event':{'matched_36h':sum(x['within_36h']=='true' for x in d),'total':len(d),'matched_ratio_kn_per_mps_median':float(np.median([float(x['ratio_kn_per_mps']) for x in d if x['within_36h']=='true']))}}
for mode in ('ratio','regional_ols','no_buffer_ols'):
 z=[x for x in s if x['mode']==mode];out['sensitivity'][mode]={'hit_count':sum(abs(float(x['R10'])-1)<=.15 for x in z),'n':len(z),'median_abs_R50_minus_1':float(np.median([abs(float(x['R50'])-1) for x in z]))}
valid=[x for x in g if x.get('R10')];out['sensitivity']['gev_lmom']={'hit_count':sum(abs(float(x['R10'])-1)<=.15 for x in valid),'n':len(valid),'median_abs_R50_minus_1':float(np.median([abs(float(x['R50'])-1) for x in valid]))}
(r/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
