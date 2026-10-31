import glob,re,json
import pandas as pd
from pathlib import Path
R=Path(__file__).resolve().parent
rows=[];pat=r'\b[+-]?(?:TS(?!NO)[A-Z]*|CB)\b'
for f in sorted(R.glob('grid_*_h3.csv.gz')):
 d=pd.read_csv(f);hit=d.metar.fillna('').str.contains(pat,case=False,regex=True)
 # real TS indicator in any METAR, explicitly not TSNO (thunderstorm information not available)
 rows.append(dict(event=f.name.removeprefix('grid_').removesuffix('_h3.csv.gz'),n=int(hit.sum()),stations=int(d.loc[hit,'station'].nunique()),total=d.station.nunique()))
q=pd.DataFrame(rows).sort_values(['n','event']);q.to_csv(R/'screen_corrected_h3.csv',index=False);print(q.to_string(index=False))
