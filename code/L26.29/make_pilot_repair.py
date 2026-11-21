#!/usr/bin/env python3
"""Create a fresh, non-solving L26.29 corrected timing-pilot input."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
args = parser.parse_args()
root = args.root.resolve()
if root.exists():
    raise SystemExit(f'Refusing existing root: {root}')
subprocess.run([sys.executable, str(base/'make_pilot.py'), str(root), '--steps', '60'], check=True, stdout=subprocess.DEVNULL)

def change(rel, old, new):
    f = root/rel
    text = f.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'{rel}: expected one match, got {text.count(old)}: {old!r}')
    f.write_text(text.replace(old, new))

change('system/fvSchemes',
       'divSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); }',
       'divSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); div((nuEff*dev2(T(grad(U))))) Gauss linear; }')
change('system/controlDict', 'endTime 0.300000;\ndeltaT 0.005;', 'endTime 0.120000;\ndeltaT 0.002;')
change('run.sh', '#$ -N L26_29_pilot', '#$ -N L26_29_pilot_v3')
# The pilot uses an unchanged mesh, solver, decomposition and force-output cadence.
# The previous initial max Co was 1.0655265 at dt=.005; dt=.002 predicts .4262106.
manifest = {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob('*')) if f.is_file() and f.name != 'input_sha256.json'}
(root/'input_sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'root': str(root), 'files': len(manifest), 'sha256': manifest}, indent=2))
