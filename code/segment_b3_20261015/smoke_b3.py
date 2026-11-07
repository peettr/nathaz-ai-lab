from pathlib import Path
s=Path('/content/conus_smoke.py').read_text().replace('r2_conus_smoke_2026_attempt3.zarr','r2_conus_smoke_b3.zarr').replace('r2_conus_smoke.json','r2_conus_smoke_b3.json')
exec(compile(s,'/content/smoke_b3_generated.py','exec'),{'__name__':'__main__'})
