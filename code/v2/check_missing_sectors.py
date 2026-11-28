import pandas as pd,numpy as np
from pathlib import Path
r=Path('/content/e_terrain_v2')
f=pd.concat([pd.read_csv(p) for p in (r/'full/forecast_parts').glob('*.csv')]);f['valid']=pd.to_datetime(f.init_utc,utc=True)+pd.to_timedelta(f.lead_h,unit='h');f['sector']=((np.degrees(np.arctan2(-f.fc_u,-f.fc_v))%360)//90).astype(int)
train=set(zip(f[f.valid<'2024-01-01'].station,f[f.valid<'2024-01-01'].source,f[f.valid<'2024-01-01'].lead_h,f[f.valid<'2024-01-01'].sector))
test=f[f.valid>='2024-01-01'];missing=test[[tuple(x) not in train for x in zip(test.station,test.source,test.lead_h,test.sector)]]
print('missing sector',len(missing),missing.groupby(['station','source','lead_h','sector']).size().to_dict())
