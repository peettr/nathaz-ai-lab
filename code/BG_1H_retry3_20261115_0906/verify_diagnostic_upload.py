import hashlib
from pathlib import Path
p=Path('/content/diagnostic_extract.py')
print('DIAGNOSTIC_SHA256',hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
