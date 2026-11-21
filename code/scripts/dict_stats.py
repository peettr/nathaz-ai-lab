"""回复动作字典：可标注率与首选标签 κ。可标注 = 两位标注者都判 fits=1，且两人的标签集合（首选+次选）有交集。
用法: python3 -I dict_stats.py <labels_L1> <labels_L2>"""
import sys, json, collections
A = {json.loads(l)['unit_id']: json.loads(l) for l in open(sys.argv[1])}
B = {json.loads(l)['unit_id']: json.loads(l) for l in open(sys.argv[2])}
ids = sorted(A); assert set(ids) == set(B)
lab = lambda x: {x['primary'], x.get('secondary')} - {None}
ok = [u for u in ids if A[u]['fits'] == 1 and B[u]['fits'] == 1 and lab(A[u]) & lab(B[u])]
a = [A[u]['primary'] for u in ids]; b = [B[u]['primary'] for u in ids]; n = len(ids)
po = sum(x == y for x, y in zip(a, b)) / n
ca, cb = collections.Counter(a), collections.Counter(b)
pe = sum(ca[k] / n * cb[k] / n for k in set(a) | set(b))
print(f'n={n} 可标注={len(ok)} ({100*len(ok)/n:.1f}%) 首选一致={sum(x==y for x,y in zip(a,b))} ({100*po:.1f}%) kappa={(po-pe)/(1-pe):.2f}')
print('任一方 fits=0:', sum(1 for u in ids if A[u]['fits'] == 0 or B[u]['fits'] == 0))
for u in ids:
    if A[u]['fits'] == 0 or B[u]['fits'] == 0: print(' ', u, A[u].get('note') or '', '|', B[u].get('note') or '')
