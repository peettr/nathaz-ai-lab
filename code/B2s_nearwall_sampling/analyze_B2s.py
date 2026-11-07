from pathlib import Path
import json,csv,datetime,hashlib,numpy as np
R=Path(__file__).resolve().parent;rows=json.loads((R/'nearwall_80.json').read_text());h=json.loads((R/'hashes.json').read_text()); assert len(rows)==80 and [p['id'] for p in rows]==list(range(1,81));assert h['case/RESULTS/city_stability.csv']['sha256']=='54208a762010376e552fa9ee6576f4db977f3737b9a9e1f2357dfdbd0bc4d82c'
with (R/'nearwall_80.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','obs_ratio','wall_distance_m','sampled_Su_ratio','center_fluid','center_Su_ratio','distance_from_wall_m','line_Su_ratio','line_S_ratio','line_k_m2s2','fluid_corners','solid_weight'])
 for p in rows:
  for q in p['line']:
   w.writerow([p['id'],p['obs_W'],p['wall_distance_m'],p['original']['Su'],int(p['nearest_center']['fluid']),p['nearest_center']['Su'],q['distance_m'],q['Su'],q['S'],q['k'],q['fluid_corners'],q['solid_weight']])
with (R/'sessions.log').open('w') as f:
 f.write('Colab A100 session luw-b2s-1017; absolute config '+str(R/'sessions.json')+'\n')
 f.write('US-Eastern created 10-17 17:48:07 EDT (keepalive session creation record); inputs uploaded through 17:49:58 EDT\n')
 f.write('US-Eastern launched 10-17 17:52:25 EDT; solver 31000 steps 1920 s, completion observed 18:25:38 EDT\n')
 f.write('US-Eastern all 16 files downloaded verified 10-17 18:27:12 EDT; session terminated 10-17 18:27:18 EDT\n')
 f.write('Estimated CU at 5.4 CU/h for creation-to-stop 39m11s: 3.53 CU (approximate; slight 0.03 CU above nominal 3.5 cap; exact billing not available)\n')
 f.write('Original B2u trace sha256 '+h['case/RESULTS/city_stability.csv']['sha256']+'; 16 deliverables byte sizes and both-side SHA256 in hashes.json; local verification download_verified.txt\n')
print('CSV records',sum(1 for _ in (R/'nearwall_80.csv').open())-1)
for p in rows:
 if p['id'] in (50,51,52,54,55,74):
  print(p['id'], 'obs',round(p['obs_W'],4),'original',round(p['original']['Su'],4),'d1',round(p['line'][3]['Su'],4),'d2',round(p['line'][5]['Su'],4),'ratio2',round(p['line'][5]['Su']/p['obs_W'],3),'corner2',p['line'][5]['fluid_corners'],'solidwt2',round(p['line'][5]['solid_weight'],3))
