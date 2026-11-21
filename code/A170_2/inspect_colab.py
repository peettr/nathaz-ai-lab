# Inspect the single running smoke worker without restarting it.
from pathlib import Path
import subprocess
p=Path('/content/a170_2_smoke.log')
print('log_tail',p.read_text(errors='replace')[-3500:] if p.exists() else 'no log')
for x in ('a170_2_smoke.done','a170_2_full.done','a170_2.failed','a170_2_checkpoint.tar.gz'):
 q=Path('/content')/x
 print(x,q.exists(),q.stat().st_size if q.exists() else 0)
print('workers',subprocess.run(['pgrep','-af','colab_a170_2.py'],capture_output=True,text=True).stdout[:1500])
