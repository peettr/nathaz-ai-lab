#!/usr/bin/env python3
"""Fixture executable: emits only small synthetic artifacts, never scientific evidence."""
import os,pathlib,sys
cfg=pathlib.Path(sys.argv[1]);o=cfg.parent/'RESULTS';o.mkdir(exist_ok=True)
(o/'wall_tau_actual.csv').write_text('x,y,tau_f,force\n1,1,0.2,0.2\n')
pathlib.Path(os.environ['LUW_CAPTURE_CL']).write_text('FIXTURE_OPENCL_NOT_COMPILED\n')
print('FIXTURE_ONLY',cfg.name,flush=True)
