"""按 Lead 盲裁结果合成最终判定。分歧编号顺序与 disputes.py 一致；reject_nums 内的分歧判"不覆盖"，其余判"覆盖"。
用法: python3 -I finalize.py <root> <paper...>"""
import sys, json
root = sys.argv[1]
for p in sys.argv[2:]:
    rej = set(json.load(open(f'{root}/final/adj_{p}.json'))['reject_nums'])
    U = [json.loads(l)['unit_id'] for l in open(f'{root}/judge_in/{p}_units.jsonl')]
    J = [{}, {}]; P = [{}, {}]
    for k in (0, 1):
        for l in open(f'{root}/judge/{p}_J{k+1}.jsonl'):
            x = json.loads(l)
            if x['type'] == 'unit': J[k][x['unit_id']] = set(x['covered_by']); P[k][x['unit_id']] = set(x.get('partial_by', []))
    n = 0; nd = 0
    with open(f'{root}/final/{p}_judgments.jsonl', 'w') as f:
        for u in sorted(U):
            cov = J[0][u] & J[1][u]
            for i in sorted(J[0][u] ^ J[1][u]):
                n += 1
                if n not in rej: cov.add(i)
                else: nd += 1
            part = (P[0][u] | P[1][u] | (J[0][u] ^ J[1][u])) - cov
            f.write(json.dumps({'unit_id': u, 'covered_by': sorted(cov), 'partial_by': sorted(part)}) + '\n')
    print(p, 'disputes', n, 'rejected', nd)
