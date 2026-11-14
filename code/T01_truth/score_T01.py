#!/usr/bin/env python3
"""L22.6 T01 protocol v2 grader. Execute on CRC, never on 工作站.

Candidate curves.py must print a JSON object on its last stdout line with C1,C2 arrays.
Candidate mistakes are status L0; infrastructure failures are harness_fault.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def validate(line):
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        raise ValueError('last stdout line expected JSON object') from None
    if not isinstance(obj, dict):
        raise ValueError('last stdout line expected JSON object')
    for key in ('C1', 'C2'):
        if key not in obj:
            raise ValueError(f'missing key {key}')
        a = obj[key]
        if not isinstance(a, list):
            raise ValueError(f'{key} expected array')
        if len(a) != 601:
            raise ValueError(f'{key} length expected 601, got {len(a)}')
        for i, v in enumerate(a):
            if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v):
                raise ValueError(f'{key}[{i}] expected finite number')
    return obj


def load_truth(path):
    if not path.is_file():
        raise FileNotFoundError(f'missing truth: {path}')
    data = json.loads(path.read_text())
    assert data['n_final'] == 60000, 'truth N must be 60000'
    return {k: data['cases'][k + '_template']['q_var'] for k in ('C1', 'C2')}


def load_q(path):
    if not path.is_file():
        raise FileNotFoundError(f'missing Q: {path}')
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 601 or [int(x['t_s']) for x in rows] != list(range(601)):
        raise ValueError('invalid frozen Q grid')
    return {k: [float(x['Q_' + k + '_q_var_m2']) for x in rows] for k in ('C1', 'C2')}


def feedback(kind, text):
    if kind == 'timeout':
        return 'TimeoutError: curves.py exceeded 600 s'
    lines = text.splitlines()
    if kind == 'compile':
        return '\n'.join(lines[:200])
    if kind == 'format':
        return text
    marks = ('Error', 'Exception', 'Traceback', 'FOAM FATAL', 'Floating point exception')
    first = next((i for i, s in enumerate(lines) if any(m in s for m in marks)), len(lines))
    return '\n'.join(lines[:50] + lines[first:][-150:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('candidate', type=Path)
    ap.add_argument('--truth', type=Path, default=Path(__file__).resolve().parent/'C2/truth_C2.json')
    ap.add_argument('--q-csv', type=Path, default=Path(__file__).resolve().parent/'C2/Q_curves.csv')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--opt', action='store_true')
    a = ap.parse_args()
    result = {'schema': 'L22_6_T01_grade_v2', 'status': 'not_run', 'level': None, 'candidate': str(a.candidate)}
    def save():
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    try:
        truth = load_truth(a.truth)
        q = load_q(a.q_csv)
        if any(len(v) != 601 or not all(math.isfinite(x) for x in v) for v in truth.values()):
            raise ValueError('invalid frozen truth')
    except (OSError, ValueError, KeyError, AssertionError) as ex:
        result.update(status='harness_fault', error=str(ex)); save(); return 2
    script = a.candidate/'curves.py'
    if not script.is_file():
        result.update(status='L0', level='L0', failure='compile', feedback='FileNotFoundError: curves.py'); save(); return 0
    try:
        compile(script.read_bytes(), str(script), 'exec')
    except Exception as ex:
        result.update(status='L0', level='L0', failure='compile', feedback=feedback('compile', str(ex))); save(); return 0
    try:
        p = subprocess.run([sys.executable, 'curves.py'], cwd=a.candidate, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    except subprocess.TimeoutExpired:
        result.update(status='L0', level='L0', failure='timeout', feedback=feedback('timeout','')); save(); return 0
    except OSError as ex:
        result.update(status='harness_fault', error=str(ex)); save(); return 2
    if p.returncode:
        result.update(status='L0', level='L0', failure='runtime', feedback=feedback('runtime', p.stderr + '\n' + p.stdout)); save(); return 0
    try:
        values = validate(p.stdout.splitlines()[-1] if p.stdout.splitlines() else '')
    except ValueError as ex:
        result.update(status='L0', level='L0', failure='format', feedback=f'ValueError: {ex}'); save(); return 0
    scores = {}
    for k in ('C1', 'C2'):
        v, s, qs = values[k], truth[k], q[k]
        den = sum(x*x for x in s)
        if den <= 0 or max(s) <= 0:
            result.update(status='harness_fault', error='degenerate frozen truth'); save(); return 2
        e2 = math.sqrt(sum((x-y)**2 for x,y in zip(v,s))/den)
        ep = max(v)/max(s)-1
        qdist = max(abs(x-y)/abs(y) if y else (0 if x == 0 else math.inf) for x,y in zip(v,qs))
        constant = max(v) == min(v)
        level = 'L0' if constant else ('L1' if e2 > .10 or abs(ep) > .10 else ('L3' if e2 <= .03 and abs(ep) <= .03 else 'L2'))
        scores[k] = {'e_L2':e2, 'e_pk':ep, 'peak_time_error_s':v.index(max(v))-s.index(max(s)),
                     'max_relative_difference_Q':qdist if math.isfinite(qdist) else None,
                     'quasisteady_shortcut':qdist < .01, 'level':level}
    result.update(status='scored', level=min((scores[k]['level'] for k in scores), key=lambda x:int(x[1:])), cases=scores)
    if a.opt:
        opt = a.candidate/'opt.py'
        if opt.is_file():
            try:
                p = subprocess.run([sys.executable, 'opt.py'], cwd=a.candidate, text=True, capture_output=True, timeout=600)
                result['optional_opt'] = {'returncode':p.returncode, 'last_stdout_line':p.stdout.splitlines()[-1] if p.stdout.splitlines() else None}
            except subprocess.TimeoutExpired:
                result['optional_opt'] = {'error':'TimeoutError: opt.py exceeded 600 s'}
    save(); return 0

if __name__ == '__main__':
    sys.exit(main())
