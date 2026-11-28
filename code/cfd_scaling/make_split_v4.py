"""Freeze an expanded, geometry-disjoint internal validation split, no test-driven choices."""
import json, random, re
from pathlib import Path
root=Path(__file__).resolve().parent
s=json.loads((root/'group_split_known_direction.json').read_text())
g=lambda c:re.sub(r'_d\d+$','',c)
assert set(map(g,s['train_cases']))==set(s['train_groups'])
assert set(s['test_groups']).isdisjoint(s['train_groups']+s['val_groups'])
by={q:[c for c in s['train_cases'] if g(c)==q] for q in s['train_groups']}
rng=random.Random(20261014); groups=sorted(by);rng.shuffle(groups)
extra=[]
for q in groups:
    extra.append(q)
    if len(s['val_cases'])+sum(map(lambda x:len(by[x]),extra))>=40:break
newval=s['val_cases']+[c for q in extra for c in by[q]]
remaining=[q for q in s['train_groups'] if q not in extra]
train=[c for q in remaining for c in by[q]]
assert 39<=len(newval)<=41 and len(train)+len(newval)+len(s['test_cases'])==528
assert not (set(remaining)&(set(s['test_groups'])|set(s['val_groups'])|set(extra)))
seeds={}
for seed in (17,42,73):
    order=sorted(remaining);random.Random(seed).shuffle(order)
    nested={};acc=[]
    for q in order:
        acc+=by[q]
        for n in (50,100,200):
            if str(n) not in nested and len(acc)>=n:nested[str(n)]=acc.copy()
    nested['all']=acc.copy()
    assert set(nested['50'])<=set(nested['100'])<=set(nested['200'])<=set(acc)
    seeds[str(seed)]=nested
out={'source':'Post-hoc second-round expansion of pre-existing known-direction split; test cases/groups unchanged; validation chosen deterministically before v4 training, not independent of earlier test exposure', 'type_by_case':s['type_by_case'], 'train_cases':train,'val_cases':newval,'test_cases':s['test_cases'],'train_groups':remaining,'val_groups':s['val_groups']+extra,'test_groups':s['test_groups'],'added_validation_groups':extra,'seeds':seeds,'exclusion_record':s['exclusion_record']}
p=root/'group_split_v4.json'
assert not p.exists(),f'will not overwrite {p}'
p.write_text(json.dumps(out,indent=2,ensure_ascii=False))
print('V4_SPLIT',len(train),len(newval),len(s['test_cases']),len(remaining),len(out['val_groups']),len(out['test_groups']), {k:{n:len(v) for n,v in x.items()} for k,x in seeds.items()})
