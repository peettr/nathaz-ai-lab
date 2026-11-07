# Read the current Colab run's progress
from pathlib import Path
import os
r=Path('/content/luw_split_'+os.environ['LUW_TAG'])
for n in ('progress.log','solver.exit','extract.log','error.txt'):
 p=r/n
 if p.exists(): print(n,p.read_text()[-1800:])
print('done',(r/'all.done').exists())
