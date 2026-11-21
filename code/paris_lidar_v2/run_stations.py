from pathlib import Path
import pandas as pd
r=Path('/content/paris_a1_v2')
print('OBS_FILES',[p.name for p in sorted(r.glob('obs_*.csv'))],flush=True)
a=pd.concat((pd.read_csv(p) for p in sorted(r.glob('obs_*.csv'))),ignore_index=True)
print(a[['station','lat','lon','target_agl']].drop_duplicates().to_string(index=False),flush=True)
a[['station','lat','lon']].drop_duplicates('station').to_csv(r/'stations.csv',index=False)
