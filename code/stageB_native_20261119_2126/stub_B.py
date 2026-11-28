#!/usr/bin/env python3
"""Pipeline-only fake statistical producer; never use its data scientifically."""
import json,os,pathlib,sys
# The stub is copied into a solver bin; the fixture is supplied as absolute path.
case=json.loads(pathlib.Path(os.environ['T17_B_FIXTURE']).read_text())
case=case['cases'][os.environ['T17_B_GROUP']][os.environ['T17_B_SEED']]
out=pathlib.Path(os.environ['T17_B_OUTPUT'])
phase=os.environ['T17_B_PHASE']
if phase=='equilibrium':data={'last_T_two_half_windows':case['v0_attempts'][0]}
elif phase=='statistics':data={k:v for k,v in case.items() if k!='v0_attempts'}
else:raise SystemExit('bad phase')
out.write_text(json.dumps(data)+'\n')
print('STUB_ONLY',phase,os.environ['T17_B_GROUP'],os.environ['T17_B_SEED'])
