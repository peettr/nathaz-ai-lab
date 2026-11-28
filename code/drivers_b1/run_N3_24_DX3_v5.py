#!/usr/bin/env python3
"""N3 24h D-X3 single-cycle runner: exact-input exception, frozen science."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FROZEN = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/infer_b1_blackwell_8_v2/infer_b1_blackwell_8_v2.py')
EXPECTED_SOURCE = '99956ccef32693e107c58a07f68acdbdaf442db1ce99bb768fa167eac65e08b7'
EXPECTED_DIAGNOSTIC = '0e9ac3ed257c524eb84230e23cde55b78d4b564bc411941662d69416016acf3f'
ALLOWED = {'specific_humidity:level=35:outside_[0,.04]',
           'specific_humidity:level=36:outside_[0,.04]'}


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    from importlib import util
    spec = util.spec_from_file_location('frozen_science_dx3', FROZEN)
    science = util.module_from_spec(spec)
    spec.loader.exec_module(science)
    science.ROOT = ROOT
    assert sha(science.PARAM) == science.EXPECTED
    assert any(d.platform == 'gpu' for d in science.jax.devices())
    source = science.INPUT / 'input_2022070418_zero.nc'
    assert sha(source) == EXPECTED_SOURCE
    diag_path = ROOT / 'N3_24_Q_DX3_DIAGNOSTIC_v2.json'
    assert sha(diag_path) == EXPECTED_DIAGNOSTIC
    diagnostic = json.loads(diag_path.read_text())
    assert [r['count'] for rs in diagnostic['levels'].values() for r in rs] == [1, 2, 0, 0]
    assert all(r['count']/r['total_cells'] <= .001 and r['d01_bbox_count'] == 0
               for rs in diagnostic['levels'].values() for r in rs)
    assert all(0 <= c['q_kgkg'] <= .05 and c['below_ground']
               for rs in diagnostic['levels'].values() for r in rs for c in r['cells'])
    original = science.check

    def dx3_check(path, kind):
        assert kind == 'graphcast' and Path(path).resolve() == source.resolve()
        result = original(path, kind)  # All original D-X1 tests always run.
        assert not result['passed'] and set(result['errors']) == ALLOWED, result['errors']
        result['original_passed'] = False
        result['original_errors'] = result['errors'].copy()
        result['dx3_exception'] = {'diagnostic_sha256': EXPECTED_DIAGNOSTIC,
                                   'source_sha256': EXPECTED_SOURCE,
                                   'approved_rule': 'DEVIATIONS_GC37X.md D-X3 §2',
                                   'unchanged_input': True}
        result['errors'] = []
        result['passed'] = True
        return result

    science.check = dx3_check
    cfg = json.loads((ROOT/'event_times_bbox_gc37x.json').read_text())['events']['N3']
    science.run_one('N3', '24h', '2022070418', 5, cfg['domain'])

if __name__ == '__main__':
    main()
