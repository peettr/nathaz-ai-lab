from pathlib import Path
import os
for p in ['/content/fixture_fixed.hpp','/content/luw_wp1_precision_v2/results.json','/content/precision.log']:
 q=Path(p);print(p,q.exists(),q.stat().st_size if q.exists() else '',q.read_text(errors='replace')[-1000:] if q.exists() and q.suffix in ('.log','.json') else '')
