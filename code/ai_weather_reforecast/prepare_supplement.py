"""On Colab, derive E3-enabled scripts without touching completed results."""
from pathlib import Path
p=Path('/content/ai_weather_forecast.py')
s=p.read_text()
s=s.replace("event in ('E1','E2')", "event in ('E1','E2','E3')")
s=s.replace("'E2':'2020-06-09T06:00'", "'E2':'2020-06-09T06:00','E3':'2023-07-03T18:00'")
s=s.replace("'E2':(39.5,41.5)", "'E2':(39.5,41.5),'E3':(34.25,35.0)")
s=s.replace("'E2':(255.5,258.5)", "'E2':(255.5,258.5),'E3':(260.25,261.0)")
s=s.replace("suffix='grid25_rhproxy_v3' if model_name=='FuXi' else 'grid25'", "suffix='supp_rhproxy' if model_name=='FuXi' else 'supp'")
s=s.replace("v in ('sp','msl')", "v in ('sp','msl','d2m')")
assert "'E3':'2023-07-03T18:00'" in s
Path('/content/ai_weather_forecast_supp.py').write_text(s)
p=Path('/content/ai_weather_truth.py')
s=p.read_text()
s=s.replace("('E2','2020-06-09T06:00',(39.5,41.5),(255.5,258.5))", "('E2','2020-06-09T06:00',(39.5,41.5),(255.5,258.5)),('E3','2023-07-03T18:00',(34.25,35.0),(260.25,261.0))")
s=s.replace("for event,valid,latb,lonb in [", "for event,valid,latb,lonb in [")
s=s.replace("for tag,t in times.items():", "for tag,t in times.items():\n  if event in ('E1','E2') and tag not in ('valid',):continue")
s=s.replace("truth_{event}_{tag}_v2.npz", "truth_{event}_{tag}_supp.npz")
assert "('E3','2023-07-03T18:00'" in s
Path('/content/ai_weather_truth_supp.py').write_text(s)
print('PREPARED')
