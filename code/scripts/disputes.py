"""列出两判分歧（盲：不含组别）。用法: python3 -I disputes.py <root> <paper>"""
import sys, json
root, p = sys.argv[1], sys.argv[2]
U = {json.loads(l)['unit_id']: json.loads(l) for l in open(f'{root}/judge_in/{p}_units.jsonl')}
I = {json.loads(l)['id']: json.loads(l)['text'] for l in open(f'{root}/judge_in/{p}_items.jsonl')}
J = [{}, {}]
for k in (0, 1):
    for l in open(f'{root}/judge/{p}_J{k+1}.jsonl'):
        x = json.loads(l)
        if x['type'] == 'unit': J[k][x['unit_id']] = set(x['covered_by'])
n = 0
for u in sorted(U):
    d = sorted(J[0][u] ^ J[1][u])
    if not d: continue
    print(f"== {u}: {U[u]['object']} | {U[u]['summary_zh']} | 要求:{U[u]['request']}")
    for i in d:
        n += 1
        print(f"  [{p}#{n}] {i} ({'J1' if i in J[0][u] else 'J2'}判覆盖): {I[i][:230]}")
