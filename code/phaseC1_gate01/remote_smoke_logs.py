import os
for p in os.listdir('/content'):
 if p.endswith('_smoke.log'):
  print(p,open('/content/'+p).read()[-400:])
