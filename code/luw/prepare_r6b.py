"""Fresh r6b solve: averaging window itself spans domain flow-through."""
from pathlib import Path
p=Path(__file__).parent
for src,dst in [('bootstrap_r6.py','bootstrap_r6b.py'),('launch_r6.py','launch_r6b.py'),('extract_r6.py','extract_r6b.py')]:
 t=(p/src).read_text().replace('/content/luw-aij-r6','/content/luw-aij-r6b')
 if src=='bootstrap_r6.py':
  assert t.count('purge_avg = 11000')==1
  t=t.replace('purge_avg = 11000','purge_avg = 20000')
 if src=='extract_r6.py':
  assert t.count('offset_samples_r6.json')==1
  t=t.replace('offset_samples_r6.json','offset_samples_r6b.json')
 dest=p/dst;assert not dest.exists();dest.write_text(t);compile(t,str(dest),'exec')
 print(dest)
