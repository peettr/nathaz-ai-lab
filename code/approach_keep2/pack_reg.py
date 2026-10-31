import zipfile
from pathlib import Path
with zipfile.ZipFile('/content/wale_reg_evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for tag in ('SMAG','WALE'):
  for n in ('solver.log','build.log'):
   p=Path('/content/reg_'+tag)/n
   if p.exists():z.write(p,arcname=tag+'_'+n)
