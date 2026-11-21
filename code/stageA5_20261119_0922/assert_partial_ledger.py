#!/usr/bin/env python3
"""Fail-closed A1/A3 partial host-ledger checks; NOT A7 qualification."""
import argparse
import csv
import json
import math
from pathlib import Path


def check(path: Path, expected_columns=256 * 128, limit=1e-5, unforced=False):
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2 or int(rows[0]['step']) != 0 or int(rows[-1]['step']) != 1000:
        raise ValueError('missing 0..1000 step endpoints')
    if any(int(r['eligible_native_columns']) != expected_columns for r in rows):
        raise ValueError('A3 native flags mismatch')
    if any(not math.isfinite(float(r[k])) for r in rows for k in ('mass_fluid_lattice','px_fluid_lattice')):
        raise ValueError('nonfinite M/Px')
    mass0, mass1 = (float(r['mass_fluid_lattice']) for r in (rows[0], rows[-1]))
    px0, px1 = (float(r['px_fluid_lattice']) for r in (rows[0], rows[-1]))
    if mass0 <= 0 or (unforced and px0 == 0):
        raise ValueError('invalid normalization')
    mdrift = abs(mass1-mass0)/mass0
    pdrift = abs(px1-px0)/abs(px0) if unforced else None
    result={'A1a_mass_relative_change':mdrift,'A3_native_columns':expected_columns,
            'A1b_px_relative_change':pdrift,'A7':'NOT_EVALUATED_ground_force_nan'}
    if mdrift > limit or (unforced and pdrift > limit):
        raise AssertionError(json.dumps(result))
    # Never use the placeholder ground force as an A7 measurement.
    if any(r['ground_force_x_lattice'].strip().lower() != 'nan' for r in rows):
        raise ValueError('unexpected ground-force producer: review before A7')
    return result


def fixture():
    from tempfile import TemporaryDirectory
    header='step,mass_fluid_lattice,px_fluid_lattice,ground_force_x_lattice,eligible_native_columns\n'
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/'ledger.csv'
        def put(last_mass,last_px,cols=32768):
            p.write_text(header+f'0,100,50,nan,32768\n1000,{last_mass},{last_px},nan,{cols}\n')
        put(100.0001,50.0001)
        good=check(p,unforced=True)
        for label,args in [('mass',(101,50,32768)),('px',(100,51,32768)),('flags',(100,50,32767))]:
            put(*args)
            try: check(p,unforced=True)
            except (AssertionError,ValueError): continue
            raise AssertionError('negative fixture passed: '+label)
    return {'positive':good,'negative_rejected':['mass','px','flags']}


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--fixture',action='store_true');ap.add_argument('--csv',type=Path);ap.add_argument('--unforced',action='store_true')
    a=ap.parse_args();print(json.dumps(fixture() if a.fixture else check(a.csv,unforced=a.unforced),indent=2))
