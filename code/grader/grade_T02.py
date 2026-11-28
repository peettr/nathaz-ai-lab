#!/usr/bin/env python3
"""T02 frozen numeric grader; run candidate on CRC compute node only.

Usage: grade_T02.py CANDIDATE_DIR --truth calib_T02.csv --out grade.json
The grader itself uses the Python stdlib; candidate is restricted to numpy/scipy
by the frozen prompt (this does not sandbox imports or filesystem access).
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

CASES = ('small', 'medium', 'large', 'X')
LIMIT = 600
MARK = re.compile(r'Error|Exception|Traceback|FOAM FATAL|Floating point exception')


def feedback(kind, log):
    if kind == 'timeout':
        return 'TimeoutError: t02.py exceeded 600 s\n'
    if kind == 'format':
        return log.rstrip('\n') + '\n'
    lines = log.splitlines(keepends=True)
    if kind == 'compile':
        return ''.join(lines[:200])
    hit = next((i for i, line in enumerate(lines) if MARK.search(line)), None)
    if hit is None:
        return ''.join(lines[:50])
    return ''.join(lines[:50] + lines[hit:][-150:])


def validate(line):
    try:
        data = json.loads(line)
    except (ValueError, TypeError) as exc:
        raise ValueError('last stdout line is not JSON') from exc
    if not isinstance(data, dict):
        raise ValueError('last stdout line must be a JSON object')
    for case in CASES:
        if case not in data or not isinstance(data[case], dict):
            raise ValueError(f'{case}: missing object')
        for key in ('sigma_q', 'sigma_stroke'):
            val = data[case].get(key)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
                raise ValueError(f'{case}.{key}: expected finite positive number')
    return data


def reference(path):
    with open(path, newline='') as handle:
        rows = list(csv.DictReader(handle))
    ref = {r['case']: r for r in rows if r['method'] == 'MC'}
    if set(ref) != set(CASES):
        raise RuntimeError('harness_fault: missing MC reference cases')
    return {case: {'sigma_q': float(ref[case]['sigma_q_m']),
                   'sigma_stroke': float(ref[case]['sigma_stroke_m'])} for case in CASES}


def score(data, truth):
    errors = {}
    margins = []
    for case in CASES:
        errors[case] = {}
        for key in ('sigma_q', 'sigma_stroke'):
            e = data[case][key] / truth[case][key] - 1
            errors[case][key] = e
            for level, threshold in (('L3', .10 if key == 'sigma_q' else .30),
                                     ('L2', .25 if key == 'sigma_q' else .60)):
                margins.append({'case': case, 'metric': key, 'threshold': level,
                                'limit': threshold, 'signed_margin': threshold - abs(e),
                                'absolute_distance': abs(threshold - abs(e))})
    maxq = max(abs(errors[c]['sigma_q']) for c in CASES)
    maxs = max(abs(errors[c]['sigma_stroke']) for c in CASES)
    level = 'L3' if maxq <= .10 and maxs <= .30 else 'L2' if maxq <= .25 and maxs <= .60 else 'L1'
    nearest = min(margins, key=lambda r: r['absolute_distance'])
    return {'status': 'scored', 'level': level, 'errors': errors,
            'max_absolute_error': {'sigma_q': maxq, 'sigma_stroke': maxs},
            'nearest_threshold': nearest,
            'nu_opt': {c: data[c].get('nu_opt') for c in CASES}}


def run(candidate, truth, work, timeout=LIMIT):
    reference_data = reference(truth)  # missing truth is a harness fault, never L0
    source = candidate / 't02.py'
    if not source.is_file():
        return {'status': 'candidate_failed', 'level': 'L0', 'failure_type': 'no_source',
                'feedback': 'ValueError: no complete source delivered\n'}
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    try:
        # Compile in memory: never write __pycache__ into the read-only candidate.
        compile(source.read_bytes(), str(source), 'exec')
    except (SyntaxError, UnicodeError) as exc:
        log = f'{type(exc).__name__}: {exc}\n'
        return {'status': 'candidate_failed', 'level': 'L0', 'failure_type': 'compile',
                'feedback': feedback('compile', log), 'log': log}
    try:
        process = subprocess.run([sys.executable, '-B', str(source)], cwd=work, env=env,
                                 capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {'status': 'candidate_failed', 'level': 'L0', 'failure_type': 'timeout',
                'feedback': feedback('timeout', ''), 'log': str(exc)}
    except OSError as exc:
        return {'status': 'harness_fault', 'level': None, 'error': str(exc)}
    log = process.stdout + process.stderr
    if process.returncode:
        return {'status': 'candidate_failed', 'level': 'L0', 'failure_type': 'runtime',
                'feedback': feedback('runtime', log), 'log': log}
    try:
        last = process.stdout.splitlines()[-1] if process.stdout.splitlines() else ''
        parsed = validate(last)
    except ValueError as exc:
        msg = f'ValueError: {exc}'
        return {'status': 'candidate_failed', 'level': 'L0', 'failure_type': 'format',
                'feedback': feedback('format', msg), 'log': log}
    result = score(parsed, reference_data)
    result['candidate_stdout'] = process.stdout
    result['candidate_stderr'] = process.stderr
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('candidate', type=Path)
    ap.add_argument('--truth', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--work', type=Path, default=Path.cwd())
    args = ap.parse_args()
    result = run(args.candidate.resolve(), args.truth.resolve(), args.work.resolve())
    args.out.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'level': result.get('level'), 'out': str(args.out)}))

if __name__ == '__main__':
    main()
