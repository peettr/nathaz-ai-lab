"""R4 v4 synthetic regression/branch assertions; never reads the frozen cohort."""
import csv
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / 'synthetic_selftest_1108d'
BASE = [json.loads(s) for s in (SRC / 'rows.jsonl').read_text().splitlines()]
EXPECTED = {'pass': '通过', 'fail_hit': '不通过', 'fail_false': '不通过',
            'fail_peak': '不通过', 'undecided': '不判', 'exploratory': '探索性'}
CONFIG = {'pass': (28, 27, 19, 20), 'fail_hit': (20, 27, 19, 20),
          'fail_false': (28, 27, 27, 20), 'fail_peak': (25, 30, 19, 20),
          'undecided': (28, 27, 19, 20), 'exploratory': (28, 27, 19, 20)}


def make_rows(name):
    rows = json.loads(json.dumps(BASE))
    ea, eh, ca, ch = CONFIG[name]
    for row in rows:
        event = row['unit_index'] % 2 == 0
        order = row['unit_index'] // 2
        if row['kind'] == 'baseline':
            h = eh if event else (27 if name == 'pass' and order < 20 else ch)
            for key in ('fg_wide', 'fg_narrow', 'hrrr_formula_wide'):
                row[key]['ms'] = h
        else:
            v = ea if event else ca
            for method in row['methods'].values():
                for window in method.values():
                    window['ms'] = v
    return rows


def run_case(name, rows, dest, *, controls=None, flag=None, expect_error=False):
    sub = dest / name
    sub.mkdir(exist_ok=True)
    inp = sub / 'rows.jsonl'
    expected_rows = ''.join((json.dumps(row) if not isinstance(row, str) else row) + '\n' for row in rows)
    if inp.exists():
        assert inp.read_text() == expected_rows, (name, 'existing synthetic matrix differs')
    else:
        inp.write_text(expected_rows)
    if (sub / 'score.json').exists() and not expect_error:
        return json.loads((sub / 'score.json').read_text())
    cmd = [sys.executable, str(ROOT / 'r4_score_v4.py'), '--events', str(SRC / 'events.csv'),
           '--controls', str(controls or SRC / 'controls.csv'), '--input', str(inp),
           '--output', str(sub / 'score.json')]
    if flag:
        cmd.append(flag)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if expect_error:
        assert proc.returncode != 0, (name, proc.stdout)
        return {'error': proc.stderr.strip().splitlines()[-1]}
    assert proc.returncode == 0, (name, proc.stderr)
    return json.loads((sub / 'score.json').read_text())


def test_rerun(dest):
    rows = make_rows('pass')
    # First attempt of unit 0 was interrupted; rerun replaces the entire unit,
    # including the baseline, rather than combining first and second attempts.
    first = [r for r in rows if r['unit_index'] == 0]
    for r in first:
        if r['kind'] == 'member':
            r['methods']['diagnostic']['wide']['ms'] = 5
        if r['kind'] == 'baseline':
            r['fg_wide']['ms'] = 5
        r['rerun_attempt'] = 1
    second = json.loads(json.dumps(first))
    for r in second:
        r['rerun_attempt'] = 2
        if r['kind'] == 'member':
            r['methods']['diagnostic']['wide']['ms'] = 28
        else:
            r['fg_wide']['ms'] = 27
    allrows = [r for r in rows if r['unit_index'] != 0] + first + second
    result = run_case('rerun', allrows, dest)
    assert result['cohort']['event'] == result['cohort']['control'] == 100
    assert result['main']['point']['hit_ai'] == 1.0
    assert result['main']['point']['hit_hrrr'] == 1.0
    assert result['gates']['verdict'] == '通过'
    return {'expected': '通过', 'actual': result['gates']['verdict'], 'rerun_event_n': result['cohort']['event']}


def test_variant_missing(dest):
    rows = make_rows('pass')
    for row in rows:
        if row['unit_index'] == 0 and row['kind'] == 'member':
            row['methods']['factor16777']['wide']['ms'] = None
            row['methods']['hrrrcast_without_vvel']['wide']['ms'] = None
            row['methods']['diagnostic']['narrow']['ms'] = None
        if row['unit_index'] == 0 and row['kind'] == 'baseline':
            row['fg_narrow']['ms'] = None
            row['hrrr_formula_wide']['ms'] = None
    result = run_case('variant_missing', rows, dest)
    assert result['cohort']['event'] == result['cohort']['control'] == 100
    assert result['main']['point']['hit_ai'] == 1.0
    assert all(result['report_only'][key]['cohort']['event'] == 99 for key in
               ('factor16777', 'hrrrcast_without_vvel', 'narrow', 'same_formula_hrrr'))
    assert result['gates']['verdict'] == '通过'
    return {'expected': '通过', 'actual': result['gates']['verdict'], 'main_events': 100,
            'variant_events': 99}


def test_bad_lines(dest):
    result = run_case('bad_lines', make_rows('pass') + ['{bad', '{bad'], dest)
    assert result['invalid_json_lines'] == 2
    assert any('不可解析' in w for w in result['warnings'])
    assert result['gates']['verdict'] == '通过'
    return {'invalid_json_lines': 2, 'warning': result['warnings']}


def test_duplicate_without_rerun(dest):
    rows = make_rows('pass')
    return run_case('duplicate_unmarked', rows + [json.loads(json.dumps(rows[0]))], dest, expect_error=True)


def test_missing_s0_not_exclusion(dest):
    rows = make_rows('pass')
    controls = dest / 'controls_missing.csv'
    source = list(csv.DictReader((SRC / 'controls.csv').open()))
    source[0]['phase'] = 'missing'
    with controls.open('x', newline='') as f:
        writer = csv.DictWriter(f, source[0].keys()); writer.writeheader(); writer.writerows(source)
    result = run_case('missing_s0', rows, dest, controls=controls)
    assert result['cohort']['control'] == 99
    assert result['gates']['exploratory'] is False
    return {'control': 99, 'exploratory': False}


def test_posthoc_false(dest):
    result = run_case('posthoc_false', make_rows('pass'), dest)
    item = result['without_orders_23_35_49_false_alarm']
    assert item['cohort']['control'] == 97
    assert item['point']['false_diff'] < 0
    assert item['ci']['false_diff']['lower05'] <= item['point']['false_diff'] <= item['ci']['false_diff']['upper95']
    return {'control': 97, 'point': item['point']['false_diff'], 'ci': item['ci']['false_diff']}


def main():
    assert len(BASE) == 2200
    # Keep generated matrices separate from the real inputs and from previous v3 runs.
    outdir = ROOT / 'synthetic_selftest_v4_full_1108'
    outdir.mkdir(exist_ok=True)
    results = {}
    for name, expected in EXPECTED.items():
        sub = outdir / name
        r = run_case(name, make_rows(name), outdir, flag='--s0-gate' if name == 'exploratory' else None)
        assert r['cohort']['event'] == r['cohort']['control'] == 100
        assert r['main']['valid_draws'] == 5000
        assert r['gates']['verdict'] == expected, (name, r['gates'])
        results[name] = {'expected': expected, 'actual': r['gates']['verdict'], 'valid_draws': 5000}
        print(name, results[name], flush=True)
    for name, func in [('rerun', test_rerun), ('variant_missing', test_variant_missing),
                       ('bad_lines', test_bad_lines), ('duplicate_unmarked', test_duplicate_without_rerun),
                       ('missing_s0', test_missing_s0_not_exclusion), ('posthoc_false', test_posthoc_false)]:
        results[name] = func(outdir)
        print(name, results[name], flush=True)
    (outdir / 'assertions.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print('ALL_V4_ASSERTIONS_PASSED', outdir / 'assertions.json', flush=True)


if __name__ == '__main__':
    main()
