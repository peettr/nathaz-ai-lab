import json,pathlib
r=pathlib.Path('/content/L26_18_v3');d=json.loads((r/'sfmr_centers.json').read_text())
for x in d['candidates']:
 print('\n',x['flight'],len(x['candidates']))
 for y in x['candidates'][:25]: print(y['time'],f"({y['lat']:.2f},{y['lon']:.2f})",'prom',round(y['prominence'],1),'min',round(y['smooth'],1))
