"""Frozen case-random comparison, stratified to match grouped v4 type counts."""
import json
from pathlib import Path
import random

root=Path(__file__).resolve().parent
src=json.loads((root/'group_split_v4.json').read_text())
rng=random.Random(20261014)
cohorts={}
for typ in ('ideal','real'):
    cases=sorted(c for c,t in src['type_by_case'].items() if t==typ)
    rng.shuffle(cases)
    n_train=sum(src['type_by_case'][c]==typ for c in src['train_cases'])
    n_val=sum(src['type_by_case'][c]==typ for c in src['val_cases'])
    cohorts[typ]=(cases[:n_train],cases[n_train:n_train+n_val],cases[n_train+n_val:])
split={'source':'Post-hoc case-random diagnostic, NOT gate/selection; RNG 20261014, stratified by ideal/real to match v4 train/val/test counts; direction-known cases only; no grouped isolation', 'type_by_case':src['type_by_case'], 'train_cases':sorted(cohorts['ideal'][0]+cohorts['real'][0]), 'val_cases':sorted(cohorts['ideal'][1]+cohorts['real'][1]), 'test_cases':sorted(cohorts['ideal'][2]+cohorts['real'][2])}
assert len(split['train_cases'])==377 and len(split['val_cases'])==40 and len(split['test_cases'])==111
assert len(set(split['train_cases']+split['val_cases']+split['test_cases']))==528
group=lambda c:c.rsplit('_d',1)[0]
for cohort in ('train','val','test'):
    split[cohort+'_groups']=sorted(set(map(group,split[cohort+'_cases'])))
split['overlap_groups']={a+'_'+b:sorted(set(split[a+'_groups'])&set(split[b+'_groups'])) for a,b in [('train','val'),('train','test'),('val','test')]}
path=root/'case_random_split_v4.json'
assert not path.exists(), 'Refuse overwrite frozen split'
path.write_text(json.dumps(split,indent=2,ensure_ascii=False)+'\n')
print(path, {k:len(v) for k,v in split['overlap_groups'].items()})
