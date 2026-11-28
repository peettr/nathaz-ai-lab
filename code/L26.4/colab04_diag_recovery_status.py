import pathlib,subprocess
p=pathlib.Path('/content/l264diag04')
for name in ['diag_recovery.log','forecast_air_original_retry.log','forecast_air_shift_retry.log','forecast_surface_original_retry.log','forecast_surface_shift_retry.log','comparison_retry.log']:
 f=p/name;print(name,'MISSING' if not f.exists() else repr(f.read_text(errors='replace').splitlines()[-8:]))
for name in ['diag_recovery.done','diag_recovery.failed']:
 f=p/name;print(name,f.exists(),f.read_text()[-900:] if f.exists() and name.endswith('failed') else '')
print(subprocess.run(['ps','-eo','pid,etime,args'],capture_output=True,text=True).stdout[-2000:])
