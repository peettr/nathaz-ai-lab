import hashlib
from pathlib import Path
for name in ('try12_noshear_wall.csv','try12_native_wall.csv','try12_noshear_pulse.csv'):
    p=Path('/content')/name
    print(name, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest(), flush=True)
