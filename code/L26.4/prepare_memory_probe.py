#!/usr/bin/env python3
"""Prepare an isolated AIR script copy for one-init memory diagnosis."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
run = Path(sys.argv[2])
original = root / 'repo/AERO_ODE/AERO_AIR_WD/test_film_wb.py'
text = original.read_text()
header = '''import sys as _sys
_sys.path.insert(0, "{repo}")
_sys.path.insert(0, "{air}")
from common.paths import ROOT
'''.format(repo=root / 'repo/AERO_ODE', air=original.parent)
old = '''import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(next(_p for _p in _pathlib.Path(__file__).resolve().parents
                             if (_p / "common" / "paths.py").is_file())))
from common.paths import ROOT
'''
assert text.count(old) == 1
text = text.replace(old, header)
needle = '''                if log and (batch_idx % 10 == 0 or batch_idx + 10 >= len(loader)):'''
assert text.count(needle) == 1
text = text.replace(needle, '''                print("MEM_PROBE_BATCH", batch_idx, "torch_alloc_GiB", torch.cuda.memory_allocated()/2**30, "torch_reserved_GiB", torch.cuda.memory_reserved()/2**30, "torch_peak_alloc_GiB", torch.cuda.max_memory_allocated()/2**30, flush=True)
''' + needle)
(run / 'test_film_wb_probe.py').write_text(text)
