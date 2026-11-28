from pathlib import Path
import csv, hashlib, json
ROOT = Path(__file__).resolve().parent
SPOOL = Path('./luw_tmp') / ROOT.name
NAME = 'session_luw-t17b3-b65b60624'
SOURCES = [SPOOL / NAME / 'evidence', ROOT / NAME / 'evidence']
rows = []
checks = {}
for source in SOURCES:
    bad = []
    sidecars = list(source.glob('*.sha256'))
    for sidecar in sidecars:
        file = source / sidecar.name[:-7]
        expected = sidecar.read_text().strip().split()[0]
        actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
        if actual != expected:
            bad.append(file.name)
    checks[str(source)] = {'sidecars': len(sidecars), 'bad': bad}
    assert not bad and len(sidecars) >= 24, (source, bad)
evidence = SOURCES[0]
assert json.loads((evidence / 'run.done').read_text())['verified'] == ['t15_s1', 't15_s2']
seeds = {}
for seed in (1, 2):
    prefix = f't15_s{seed}'
    case = json.loads((evidence / (prefix + '_case.json')).read_text())
    windows = json.loads((evidence / (prefix + '_windows.json')).read_text())
    assert len(case['profile_u']) == 64 and len(case['blocks']) == 4
    assert len(windows) == 13 and [w['window'] for w in windows] == list(range(1, 14))
    attempts = case['v0_attempts']
    assert len(attempts) == 1 and all(x['pass'] for x in attempts[0])
    assert (evidence / (prefix + '_v0_0.decision')).read_text().strip() == 'pass'
    seeds[prefix] = {'case_sha256': hashlib.sha256((evidence / (prefix + '_case.json')).read_bytes()).hexdigest(), 'windows_sha256': hashlib.sha256((evidence / (prefix + '_windows.json')).read_bytes()).hexdigest(), 'v0_additions': len(attempts)-1, 'v0': attempts, 'statistics_end': case['native_provenance']['statistics_end'], 'windows': len(windows)}
    for w in windows:
        rows.append({'seed': seed, 'window': w['window'], 'T_start': w['T_range'][0], 'T_end': w['T_range'][1], 'step_start': w['step_range'][0], 'step_end': w['step_range'][1], 'V1_ratio': w['V1_ratio'], 'V3_Rx_half': w['R_uu_x_half'], 'V3_Ry_half': w['R_uu_y_half'], 'Px_mean': w['Px_mean'], 'e_2p5': w['e_2p5'], 'S2b_rms': w['S2b_rms'], 'S3_max_abs_difference': w['S3_max_abs_difference']})
with (ROOT / 'T15_2T_WINDOWS_RECONCILED.csv').open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
report = {'source': str(SPOOL), 'checks': checks, 'seeds': seeds, 'windows_csv': str(ROOT / 'T15_2T_WINDOWS_RECONCILED.csv'), 'run_done_sha256': hashlib.sha256((evidence / 'run.done').read_bytes()).hexdigest()}
(ROOT / 'T15_RECOVERY_RECONCILED.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'checks': checks, 'seeds': seeds, 'window_rows': len(rows), 'report': str(ROOT / 'T15_RECOVERY_RECONCILED.json')}, ensure_ascii=False))
