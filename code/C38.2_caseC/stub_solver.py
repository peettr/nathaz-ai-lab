#!/usr/bin/env python3
"""Local dry-run substitute for the solver; never writes physical output."""
import pathlib, sys
assert len(sys.argv)==2 and pathlib.Path(sys.argv[1]).is_file()
s=pathlib.Path(sys.argv[1]).read_text()
assert 'run_nstep' in s and 'purge_avg_stride' in s
print('STUB_SOLVER_OPENED',sys.argv[1],flush=True)
