"""L26.9 两判一致性与分歧清单。用法: python3 -I agree.py <root> <paper...>"""
import sys, json, os
root = sys.argv[1]
for p in sys.argv[2:]:
    J = [{}, {}]
    for k in (0, 1):
        for l in open(f'{root}/judge/{p}_J{k+1}.jsonl'):
            x = json.loads(l)
            if x['type'] == 'unit': J[k][x['unit_id']] = set(x['covered_by'])
    items = [json.loads(l)['id'] for l in open(f'{root}/judge_in/{p}_items.jsonl')]
    units = sorted(J[0]); assert set(units) == set(J[1]), p
    a = [i in J[0][u] for u in units for i in items]; b = [i in J[1][u] for u in units for i in items]
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n; pa = sum(a) / n; pb = sum(b) / n; pe = pa*pb + (1-pa)*(1-pb)
    d = sum(len(J[0][u] ^ J[1][u]) for u in units)
    print(p, 'J1+', sum(a), 'J2+', sum(b), 'both', sum(x and y for x, y in zip(a, b)), 'diff', d, 'kappa %.2f' % ((po-pe)/(1-pe)))
