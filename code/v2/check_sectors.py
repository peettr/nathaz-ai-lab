import pandas as pd,numpy as np
from pathlib import Path
r=Path('/content/e_terrain_v2')
f=pd.concat([pd.read_csv(p) for p in (r/'full/forecast_parts').glob('*.csv')]);f['valid']=pd.to_datetime(f.init_utc,utc=True)+pd.to_timedelta(f.lead_h,unit='h');f=f[f.valid<'2024-01-01']
f['sector']=((np.degrees(np.arctan2(-f.fc_u,-f.fc_v))%360)//90).astype(int)
c=f.groupby(['station','source','lead_h','sector']).size();print('counts',c.min(),c.nsmallest(20).to_dict())
