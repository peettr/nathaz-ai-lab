#!/usr/bin/env python3
"""Correct only staged v4 submit files before first submission."""
from pathlib import Path
base = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
for lead in ('24', '48'):
    root = base / f'infer_b1_blackwell_recover_N3_{lead}_v4'
    assert not (root / 'attempt.claim').exists()
    path = root / f'recover_N3_{lead}_v4.sub'
    text = path.read_text()
    old = f'run_recover_N3_{lead}_v3.sh'
    new = f'run_recover_N3_{lead}_v4.sh'
    assert text.count(old) == 1 and (root / new).is_file()
    path.write_text(text.replace(old, new))
    print(path)
