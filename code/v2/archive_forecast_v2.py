from pathlib import Path
import zipfile
r=Path('/content/e_terrain_v2');p=r/'full/forecast_parts';assert len(list(p.glob('*.csv')))+len(list(p.glob('ERROR_*.txt')))==1464
with zipfile.ZipFile(r/'forecast_parts_v2.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in p.iterdir():z.write(f,arcname=f.name)
 z.write(r/'forecast_v2.log',arcname='forecast_v2.log')
print('FORECAST_ARCHIVED',len(zipfile.ZipFile(r/'forecast_parts_v2.zip').namelist()),(r/'forecast_parts_v2.zip').stat().st_size,flush=True)
