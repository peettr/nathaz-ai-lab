"""Run only keys absent from frozen L26.22-02e scoring; reuse its exact row_for.
No alteration to scoring_v2 or original source. New results are append-only.
"""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / 'scoring_v2b'
EXPECTED = {
    'scoring_v2/score_driver.py': '1ea6033fc7cfbb178803f0e9ae769edecb5ab2c96cf1cd666c58deffe21f8811',
    'frozen_config_v2.json': 'c057cdf53eb5348142c0bac938fda264da982610360dc379e12debba44042544',
    'method_g.py': '60cca39694e22dd5a8c3097172346a3cb2da4ca76d0ad5793dda7026cce0f75e',
    'tune_v1/optimized.py': 'fcfab1e9480fb255a2453013161f543205a8c15244a5f9d8541198c1d0872390',
    'from_L30.1f/v8b/scoring.json': '15b2c59ffabeeaf67117595ee1d396e1a0c1fe479d6b79a84f2ab0d208e4ee87',
    'scoring_v2/results_G.jsonl': 'a8f5d634e240a4ed855c313253a177801280f29209db2187f34019d76c3ca4f0',
}

def main():
    for name, digest in EXPECTED.items():
        actual = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        assert actual == digest, (name, actual)
    print('HASH_MATCH original code, config, inputs and 693 rows', flush=True)
    source = ROOT/'scoring_v2/score_driver.py'
    spec = importlib.util.spec_from_file_location('frozen_score_driver_1749057', source)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    entries = json.loads((ROOT/'from_L30.1f/v8b/scoring.json').read_text())
    seen = set()
    for line in (ROOT/'scoring_v2/results_G.jsonl').read_text().splitlines():
        row = json.loads(line)
        assert row['official_valid']
        key = (row['object'], row['event'], row['seed'])
        assert key not in seen
        seen.add(key)
    assert len(seen) == 693
    wanted = [(entry,ev,seed_no) for entry in entries for ev in original.EVENTS for seed_no in (1,2,3)
              if (entry['index'],ev[0],seed_no) not in seen]
    assert len(wanted)==171
    assert not (HERE/'results_G.jsonl').exists()
    frozen=json.loads((ROOT/'frozen_config_v2.json').read_text())
    assert frozen['group']==6 and frozen['hyper']=={'W':30.0,'lr':0.01,'steps':5}
    started=time.perf_counter()
    with (HERE/'results_G.jsonl').open('x') as out:
        for n,(entry,ev,seed_no) in enumerate(wanted,1):
            # Stop before scheduler's 5h wall cap; all finished lines remain.
            if time.perf_counter()-started >= 5*3600-180:
                print('STOP 5 core-hour cap; partial rows retained',flush=True)
                return 42
            row=original.row_for(entry,ev,seed_no,frozen['hyper'])
            original.validate(row)
            assert (row['object'],row['event'],row['seed']) not in seen
            seen.add((row['object'],row['event'],row['seed']))
            out.write(json.dumps(row,allow_nan=False)+'\n')
            out.flush()
            print('SCORE_MISSING',n,'/171',flush=True)
    assert len(seen)==864
    with (HERE/'completion.json').open('x') as f:
        json.dump({'count':len(wanted),'total':len(seen),'elapsed_core_h':(time.perf_counter()-started)/3600},f,indent=2)
    return 0

if __name__=='__main__':
    sys.exit(main())
