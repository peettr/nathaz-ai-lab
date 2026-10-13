"""Correct E3 regional grid alignment; preserve first attempt separately."""
exec(open('/content/ai_weather_prepare_supplement_v2.py').read())
from pathlib import Path
p=Path('/content/ai_weather_truth_supp.py')
s=p.read_text()
s=s.replace("truth_{event}_{tag}_supp.npz", "truth_{event}_{tag}_supp_gridfix.npz")
s=s.replace("for tag,t in times.items():", "for tag,t in times.items():\n  if event != 'E3':continue")
Path('/content/ai_weather_truth_gridfix.py').write_text(s)
print('GRIDFIX_PREPARED')
