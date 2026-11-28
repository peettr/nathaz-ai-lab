"""Annual GEV from archived paired 30-year 6-hourly point time series."""
import csv
from pathlib import Path
import numpy as np
from scipy.stats import genextreme
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
rows=[]
for site in ['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']:
    with np.load(ROOT/f'points_{site}.npz') as z:
        t=z['time'];ace=z['ace'];era=z['era']
    years=t.astype('datetime64[Y]').astype(int)+1970
    assert set(years)==set(range(1979,2009))
    row={'site':site,'n_years':30}
    for label,v in [('ace',ace),('era',era)]:
        mx=np.array([v[years==yr].max() for yr in range(1979,2009)])
        shape,loc,scale=genextreme.fit(mx)
        row[f'{label}_gev_50yr_ms']=genextreme.ppf(.98,shape,loc=loc,scale=scale)
        row[f'{label}_gev_shape_scipy']=shape
    row['gev_50yr_bias_pct']=100*(row['ace_gev_50yr_ms']/row['era_gev_50yr_ms']-1)
    rows.append(row)
with (OUT/'annual_trial.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
for r in rows:print(r['site'],round(r['gev_50yr_bias_pct'],2))
print('DONE',len(rows),'sites annual GEV trial')
