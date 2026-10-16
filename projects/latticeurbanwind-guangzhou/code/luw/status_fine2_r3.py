from pathlib import Path
import re
r=Path('/content/luw-aij-r3');p=r/'fine2.log'
print((r/'fine2.exit').read_text() if (r/'fine2.exit').exists() else (r/'fine2.metrics').read_text() if (r/'fine2.metrics').exists() else 'no marker')
if p.exists():
 text=p.read_text(errors='replace');print('HEADER\n',text[2200:6500]);print('LAST\n',text[-600:].replace('\r','\n'))
