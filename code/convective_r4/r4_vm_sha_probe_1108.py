import hashlib, pathlib, json
expected={'events_r4.csv':'8a01f4e2b910df3dc05a67eef35fa054c3b2110595bf1e71f758b9e2190e90e7','controls_r4.csv':'e4eee460a2e3e6e055dbc27e5eb5eba774bd3bcafce4b0c69a015b9c34674bd1','r4_worker_v2.py':'74babd0b95df54916e886258c5708969951331ce7def56201670b34669340f1a','r4_score_v4.py':'5f479e4dc509cd61b1964c4f195b1bf7c01bc5a2bd62d0a88f47b8b4205ba382'}
for name,digest in expected.items():
    actual=hashlib.sha256(pathlib.Path('/content',name).read_bytes()).hexdigest()
    print(name,actual,actual==digest,flush=True)
    assert actual==digest
print('VM_SHA_ALL_PASS',flush=True)
