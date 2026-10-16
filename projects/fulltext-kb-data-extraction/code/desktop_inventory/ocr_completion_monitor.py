#!/usr/bin/env python3
"""Wake the scheduled completion agent only when the OCR PID stops."""
from pathlib import Path
pid=3619113
status=Path(f'/proc/{pid}/status')
if not status.exists():
    print('stopped')
else:
    line=next((line for line in status.read_text().splitlines() if line.startswith('State:')),'')
    print('stopped' if '\tZ' in line or '\tX' in line else 'running')
