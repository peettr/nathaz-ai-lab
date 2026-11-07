import json, re, random, collections
from pathlib import Path
R=Path(__file__).resolve().parent
meta={x['Folder Name']: t for t,file in [('ideal','metadata_ideal_source.json'),('real','metadata_rea_source.json')] for x in json.loads((R/file).read_text(encoding='utf-8-sig'))}
g=collections.defaultdict(list)
for c in sorted(meta):g[re.sub(r'_d\d+$','',c)].append(c)
real_single=sorted(k for k,v in g.items() if len(v)==1 and meta[v[0]]=='real')
ideal_pair=sorted(k for k,v in g.items() if len(v)==2 and meta[v[0]]=='ideal')
assert len(real_single)>=90 and len(ideal_pair)>=24,(len(real_single),len(ideal_pair))
r=random.Random(20261014);r.shuffle(real_single);r.shuffle(ideal_pair)
test=sorted(real_single[:80]+ideal_pair[:20]); val=sorted(real_single[80:90]+ideal_pair[20:24]);train=sorted(set(g)-set(test)-set(val))
assert not(set(train)&set(test) or set(train)&set(val) or set(val)&set(test))
def cases(keys):return sorted(x for k in keys for x in g[k])
assert len(cases(train))>=400 and len(cases(test))==120 and len(test)==100
seeds={}
for seed in [17,42,73]:
 keys=train.copy();random.Random(seed).shuffle(keys)
 # Nested at the case level, while grouping val/test; all N are exact and use source cases.
 order=cases([])
 for k in keys:
  members=g[k].copy();random.Random(seed+len(order)).shuffle(members);order.extend(members)
 seeds[str(seed)]={str(n):order[:n] for n in [50,100,200,400]};seeds[str(seed)]['all']=order
 for n in [50,100,200,400]:assert len(seeds[str(seed)][str(n)])==n
out={'source':'UrbanTALES metadata (538 case IDs); test 80 real singletons + 20 ideal pairs; internal validation 10 real singletons + 4 ideal pairs; geometry key strips _dNN; seed 20261014','type_by_case':meta,'test_groups':test,'val_groups':val,'train_groups':train,'test_cases':cases(test),'val_cases':cases(val),'train_cases':cases(train),'seeds':seeds}
(R/'group_split.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('cases',len(meta),'groups',len(g),'test',len(test),len(out['test_cases']),'val',len(val),len(out['val_cases']),'train',len(train),len(out['train_cases']))
