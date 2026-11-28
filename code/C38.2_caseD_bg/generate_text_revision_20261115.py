"""Text-only revision of reviewed C38.2 drafts; fail closed on changed source.

No solver or remote access. New outputs only; preserve point-value table bytes.
"""
from pathlib import Path
import hashlib
import json
import datetime

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / '04_Handoffs'
RUNS = ROOT / '06_Logs/C38.2_caseD_bg'
RATE = 8.0


def costs(folder):
    run = RUNS / folder
    state = json.loads((run / 'controller_state.json').read_text())
    assert state['event'] == 'session_stopped' and state['gpu'] == 'G4'
    lines = (run / 'controller.log').read_text().splitlines()
    created = [line for line in lines if 'session_created {' in line]
    assert len(created) == 1
    g4_epoch = datetime.datetime.strptime(created[0][:25], '%Y-%m-%d %H:%M:%S %z').timestamp()
    total = state['elapsed_session_s']
    g4 = total - (g4_epoch - state['session_created_before_epoch'])
    assert 0 < g4 < total
    assert abs(total * RATE / 3600 - state['CU_estimate']) < 1e-8
    return f'{total:.3f}', f'{total * RATE / 3600:.6f}', f'{g4:.1f}', f'{g4 * RATE / 3600:.3f}'


def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:120], text.count(old))
    return text.replace(old, new, 1)


def point_table(blob, title):
    start = blob.index(title) + len(title)
    begin = blob.index('| Kind | ID |', start)
    end = blob.find('\n\n', begin)
    return blob[begin: end if end != -1 else len(blob)]


def output(source, target, text, titles):
    assert not target.exists(), f'Will not overwrite {target}'
    original = source.read_bytes()
    old_text = original.decode('utf-8')
    for heading in titles:
        a, b = point_table(old_text, heading), point_table(text, heading)
        assert a.encode('utf-8') == b.encode('utf-8'), heading
        print('POINT_TABLE_IDENTICAL', heading, len(a.splitlines()), hashlib.sha256(a.encode()).hexdigest())
    target.write_bytes(text.encode('utf-8'))
    print('OUTPUT', target, 'sha256', hashlib.sha256(target.read_bytes()).hexdigest())


def main():
    dsrc = HANDOFF / 'C38.2_caseD_pointvalues_v3_20261115.md'
    bsrc = HANDOFF / 'C38.2_bg_pointvalues_v4_20261115.md'
    dtgt = HANDOFF / 'C38.2_caseD_pointvalues_v3.1_20261115.md'
    btgt = HANDOFF / 'C38.2_bg_pointvalues_v4.1_20261115.md'
    assert all(p.exists() for p in (dsrc, bsrc))
    assert not dtgt.exists() and not btgt.exists()
    d = dsrc.read_text()
    b = bsrc.read_text()
    d = replace_once(d, 'IoU-registered v3 draft', 'IoU-registered v3.1 text-only revision')
    d = replace_once(d, 'The executed seed line should be checked against the staged source before external release.',
        'The staged source `setup.cpp:270,287` sets the default seed to 100 and the executed configuration does not override it (review decision `R21.4_C38.2_复核裁决_00ebb765_20261115.md`, item F).')
    total, cu, g4, g4cu = costs('CaseD_v3_20261115_1001')
    d = replace_once(d,
        'Creation-before-to-confirmed-stop 988.661 s, conservative assumed rate 8.00 CU/h, estimated 2.197024 CU (not a verified bill). The failed A100 allocation call occurred before session creation and is excluded from the billed-session interval; its elapsed waiting time is not added to this estimate.',
        f'Controller timing from first allocation attempt through confirmed stop: {total} s and {cu} CU at the conservative assumed 8.00 CU/h; this includes approximately 31–32 s waiting for the unsuccessful A100 request and the short fallback overhead. The G4 allocation-success through confirmed-stop interval alone is approximately {g4} s / {g4cu} CU (whole-second event timestamps). These are estimates, not verified billing; the controller interval must not be called an isolated G4 debit.')
    d = replace_once(d,
        'Note that the Case D 2 m section contains broad ground-mask solids; upper roof cuts provide more building-specific registration evidence.',
        'The aggregate four-level IoU uniquely favours (2,2), although the 2 m level by itself slightly favours (0,2), consistent with ground-plate boundary effects. The independent review rechecked all 45 Case D buildings at the 6 m cut: each is displaced (+2,+2), and the 6 m IoU uniquely favours (+2,+2) (`R21.4_C38.2_复核裁决_00ebb765_20261115.md`, adopted note). The 6 m cut is a review cross-check, not one of the four original aggregate levels.')
    d = replace_once(d, 'Coordinate rule: x_LUW=x_C38+850 m+offset_x, y_LUW=y_C38+550 m+offset_y; sample VTK z=wall label+z_C38.',
        'Coordinate rule: x_LUW=x_C38+850 m+offset_x, y_LUW=y_C38+550 m+offset_y; sample VTK z=wall label+z_C38. S and T share 33 coordinates: 99 labelled rows represent 66 distinct sites. Preserve both labelled rows, not independent spatial observations at shared sites.')

    b = replace_once(b, 'centroid-tie-registered v4 draft', 'centroid-tie-registered v4.1 text-only revision')
    b = replace_once(b, 'Verify the staged seed source line before external release.',
        'The staged source `setup.cpp:270,287` sets the default seed to 100, with no override in the executed configuration (`R21.4_C38.2_复核裁决_00ebb765_20261115.md`).')
    b = replace_once(b, 'The C38 source contains cross-group shared coordinates; labelled rows are not independent spatial sites.',
        'Each BG case has 10 shared coordinates across groups, plus one within-group duplicate pair at (-28,28,2); 1H has 184 and 3H has 189 distinct coordinates, respectively. Labelled rows are not independent spatial sites.')
    b = replace_once(b, 'Before comparing velocities with observations, compare closed STL horizontal cuts',
        'The tie rule was written into the decision record on 11-15 10:47, before BG v4 ran. At that time the errors for the (0,2) and (2,2) candidates had not been inspected, but zero-offset BG errors had already been seen in the first draft. For registration, compare closed STL horizontal cuts')
    b = replace_once(b, 'three native centroids x=', 'three mean occupied native grid-cell centres x=')
    b = replace_once(b, 'versus the corresponding STL centres', 'versus the corresponding mean occupied discrete-STL grid-cell centres')
    b = replace_once(b, 'See `04_Decisions/R21.4_C38.2_CaseD_BG_裁决_8bdc0b13_20261115.md` (11-15 11:00 supplement).',
        'See `04_Decisions/R21.4_C38.2_CaseD_BG_裁决_8bdc0b13_20261115.md` (supplement actually written at 10:47; corrected in the appended erratum).')
    b = replace_once(b, 'identical centroid measurement.', 'identical mean-of-occupied-grid-centres measurement.')
    for name, old_elapsed, old_cu in [('BG_1H_v4_20261115_1050', '107.804', '0.239564'), ('BG_3H_v4_20261115_1050', '378.189', '0.840419')]:
        total, cu, g4, g4cu = costs(name)
        assert total == old_elapsed and cu == old_cu
        b = replace_once(b,
            f'Session creation-before-to-confirmed-stop {old_elapsed} s, conservative assumed tariff 8.00 CU/h, estimated {old_cu} CU (not an invoiced debit; failed A100 allocation before VM creation excluded).',
            f'Controller timing from first allocation attempt through confirmed stop: {total} s / {cu} CU at the conservative assumed 8.00 CU/h, including approximately 31–32 s of unsuccessful A100 waiting and short fallback overhead. Approximate G4 allocation-success to confirmed-stop interval alone: {g4} s / {g4cu} CU (whole-second event timestamps). Neither value is a verified billing debit.')
    gate_phrase = 'The native geometry gate executed before the full solver.'
    assert b.count(gate_phrase) == 2
    b = b.replace(gate_phrase,
        'A native GEOMETRY_GATE_PASS check ran before the full solver, but it was not the preregistered per-building gate (the 1H tower-top condition includes `and True` in its implementation). The per-building `v4_alignment` check below ran after the solve: it counted solid cells at the 18/58 m label layers and at a single 22/62 m layer above each roof. Thus this is post-solve evidence, not compliance with the preregistered pre-solve per-building gate.')
    b = b.replace('| Building | Base solid cells | 20 m roof cells | 60 m roof cells | Solid cells above roof |',
        '| Building | Base-layer solid cells | 18 m label-layer solid cells | 58 m label-layer solid cells | Solid cells at 22/62 m above roof (one layer) |')
    assert b.count('one layer) |') == 2
    b = b.replace('The 1H check covers nine 20 m roofs; the 3H check covers eight 20 m roofs and the one 60 m roof.',
        'For 1H, all nine buildings have solid cells at the 18 m label layer. For 3H, all nine have solid cells at 18 m, and building 5 additionally has solid cells at 58 m. These post-solve counts do not replace the preregistered per-building pre-solve gate.')
    assert b.count('For 3H, all nine') == 2
    b = b.replace('Any solid-support extraction is NOT a fluid velocity; a zero is NOT a still-air prediction and must not enter an unobstructed flow-site comparison.',
        'Any positive-weight solid-support extraction must not be used as ANY flow-field point (not just excluded from unobstructed-site comparisons). A zero is not a still-air prediction. In 3H, only the unregistered (0,0) vertical/62 has solid weight 0.5 and nonzero speed/U_H 0.034932 (about 0.0349); it is still invalid. Neither registered (2,2) nor alternative (0,2) has this mixed point.')
    assert b.count('only the unregistered (0,0) vertical/62') == 2
    output(dsrc, dtgt, d, ['### Selected-offset main points alongside zero-offset sensitivity'])
    output(bsrc, btgt, b, ['### Registered main points alongside (0,2) and (0,0) sensitivities'])
    # Independently compare both BG tables (the title appears twice).
    old, new = bsrc.read_bytes(), btgt.read_bytes()
    marker = b'### Registered main points alongside (0,2) and (0,0) sensitivities'
    assert old.count(marker) == new.count(marker) == 2
    for j in range(2):
        def table_at(blob):
            offset = -1
            for _ in range(j + 1): offset = blob.index(marker, offset + 1)
            begin = blob.index(b'| Kind | ID |', offset)
            end = blob.find(b'\n\n', begin)
            return blob[begin:end if end != -1 else len(blob)]
        a, c = table_at(old), table_at(new)
        assert a == c
        print('BG_POINT_TABLE', j + 1, 'identical_bytes', len(a), 'sha256', hashlib.sha256(a).hexdigest())

if __name__ == '__main__':
    main()
