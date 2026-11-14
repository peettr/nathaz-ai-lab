"""Stage frozen 12 Swiss station CSVs into training/test calendar slices on Colab."""
from pathlib import Path
import pandas as pd
base=Path('/content/m4');source=base/'Swiss_source';out=base/'Swiss'
assert len(list(source.glob('obs_*.csv')))==12,len(list(source.glob('obs_*.csv')))
for p in sorted(source.glob('obs_*.csv')):
 d=pd.read_csv(p,usecols=['station','time_utc','speed_ms'])
 d['time_utc']=pd.to_datetime(d.time_utc,utc=True,errors='raise')
 assert d.station.nunique()==1 and d.station.iloc[0]==p.stem.removeprefix('obs_')
 d=d.rename(columns={'time_utc':'valid_end_utc','station':'site'})
 for name,start,end in [('train','2023-10-01','2024-01-01'),('test','2024-01-01','2024-04-01')]:
  s=d[(d.valid_end_utc>=pd.Timestamp(start,tz='UTC'))&(d.valid_end_utc<pd.Timestamp(end,tz='UTC'))]
  dest=out/f'obs_{name}';dest.mkdir(parents=True,exist_ok=True)
  q=dest/(p.stem+'.csv')
  with q.open('x') as f:s.to_csv(f,index=False)
  print('SWISS_OBS',name,p.stem,len(s),flush=True)
