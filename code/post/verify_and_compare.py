"""Read-only handoff integrity and labeled legacy-grid comparison."""
import ast
import gzip
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'out_3710432'
LOGS = ROOT.parent.parent
old2 = json.loads((LOGS / 'caseA_r9_2m_tacc_v2/metrics_caseA_r9_2m.json').read_text())
old4 = json.loads((LOGS / 'caseA_r216_0b/metrics_caseA_r216_0b.json').read_text())['r9_dx4']
new = json.loads((OUT / 'metrics_r9_dx10_v2.json').read_text())
meta = json.loads((OUT / 'meta.json').read_text())
lines = (OUT / 'output.sha256').read_text().splitlines()
assert len(lines) == 8
for line in lines:
    digest, path = line.split()
    target = OUT / Path(path).name
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, path
for name in ('u', 'v', 'w', 'k', 'fluid'):
    path = OUT / f'dx10_{name}.npy.gz'
    with gzip.open(path, 'rb') as f:
        assert f.read(8) == bytes([147]) + b'NUMPY' + bytes([1, 0])
        hdr = ast.literal_eval(f.read(struct.unpack('<H', f.read(2))[0]).decode())
        assert hdr['descr'] == '<f4' and hdr['fortran_order'] is False
        assert hdr['shape'] == tuple(meta['array_shape_zyx'])
        raw = f.read()
    assert len(raw) == 4 * math.prod(hdr['shape'])
    assert all(math.isfinite(v[0]) for v in struct.iter_unpack('<f', raw)), name
    assert meta['fields'][name]['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
keys = ('n', 'n_tke', 'FAC2', 'q_abs025', 'q_rel025', 'r', 'NRMSE_range', 'NRMSE_mean', 'TKE_FAC2', 'TKE_r', 'mean_ratio', 'mixed_solid')
sections = {'vertical': ('vertical_actual', 'vertical', 'vertical'),
            '4m': ('z4_actual', 'z8', 'z8'),
            '40m': ('z40_actual', 'z80', 'z80'),
            '8m_diagnostic': ('z8_diagnostic', 'z8', 'z8'),
            '80m_diagnostic': ('z80_diagnostic', 'z80', 'z80')}
rows = []
for label, (k2, k4, k10) in sections.items():
    m2 = old2['diagnostic' if 'diagnostic' in label else 'main'][k2]['plus_xy']
    m4 = old4['diagnostic' if 'diagnostic' in label else 'primary'][k4]['selected']
    m10 = new['diagnostic' if 'diagnostic' in label else 'primary'][k10]['selected']
    rows.append({'plane': label, '2m_legacy_label_not_wall_matched': {k:m2[k] for k in keys},
                 '4m_legacy_label_not_wall_matched': {k:m4[k] for k in keys},
                 '10m_v2_wall_matched': {k:m10[k] for k in keys}})
result = {'caution': '2m and 4m archived metrics sampled VTK label z at nominal heights (plus_xy); they are NOT aligned to effective-wall height. 10m v2 is wall-matched. Values are shown in parallel for provenance, not a controlled grid convergence comparison.',
          '10m_primary_4m_interpolates_below_first_fluid_center': True,
          '10m_primary_4m_mixed_solid_selected': new['primary']['z8']['selected']['mixed_solid'],
          'metrics': rows, 'verified_sha256_count': len(lines), 'verified_fields': 5}
(ROOT / 'COMPARISON_3710432.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
print('Verified:', len(lines), 'hashes; 5 numpy gzip headers, full finite fields, byte counts. Comparison:', ROOT / 'COMPARISON_3710432.json')
for row in rows:
    print(row['plane'], 'FAC2/r/NRMSE_range/mean_ratio/mixed', [[round(r[k],4) if isinstance(r[k],float) else r[k] for k in ('FAC2','r','NRMSE_range','mean_ratio','mixed_solid')] for r in list(row.values())[1:]])
