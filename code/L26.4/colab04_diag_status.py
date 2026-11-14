import pathlib,os
p=pathlib.Path('/content/l264diag04')
for name in ['stage.log','diag_run.log','static_probe.log','build_static.log','interpolation.log','forecast_air_original.log','forecast_air_shift.log','forecast_surface_original.log','forecast_surface_shift.log','comparison.log']:
 f=p/name
 print(name, 'MISSING' if not f.exists() else f'{f.stat().st_size} bytes | '+str(f.read_text(errors='replace').splitlines()[-5:]))
for name in ['stage.done','stage.failed','diag.done','diag.failed']:
 print(name,(p/name).exists())
