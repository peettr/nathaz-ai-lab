"""Verify and join immutable 1749057 rows with scoring_v2b missing rows.
Run only after exit marker 0. Fails before writing if any key/value is invalid.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OLD=ROOT/'scoring_v2/results_1749057/results_G.jsonl'
NEW=ROOT/'scoring_v2b/results_G.jsonl'
OUT=ROOT/'scoring_v2/merged/results_G.jsonl'
OLD_SHA='a8f5d634e240a4ed855c313253a177801280f29209db2187f34019d76c3ca4f0'

def main():
    assert hashlib.sha256(OLD.read_bytes()).hexdigest()==OLD_SHA
    assert not OUT.exists()
    rows=[]; keys=set()
    for path, count in ((OLD,693),(NEW,171)):
        part=[json.loads(line) for line in path.read_text().splitlines()]
        assert len(part)==count,(path,len(part))
        for row in part:
            key=(row['object'],row['event'],row['seed'])
            assert key not in keys,key
            keys.add(key)
            assert row['official_valid'] is True and len(row['e'])==3 and len(row['last_e'])==3
            assert isinstance(row['best_iteration'],int) and 1<=row['best_iteration']<=25
            rows.append(row)
    entries=json.loads((ROOT/'from_L30.1f/v8b/scoring.json').read_text())
    expected={(entry['index'],f'EVT{i:02}',seed) for entry in entries for i in range(1,13) for seed in (1,2,3)}
    assert len(expected)==864 and keys==expected,(len(keys),len(expected),expected-keys,keys-expected)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('x') as f:
        for row in rows:
            f.write(json.dumps(row,allow_nan=False)+'\n')
    digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps({'rows':len(rows),'unique':len(keys),'official_valid':len(rows),'sha256':digest,'output':str(OUT)}))
if __name__=='__main__':main()
