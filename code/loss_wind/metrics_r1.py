#!/usr/bin/env python3
"""Read-only aggregation of frozen r1 answers, gold labels, and source metadata.
Does not replace the narrative-only model labels or rewrite prior analysis.json.
"""
import csv,json,pathlib,collections,re
P=pathlib.Path(__file__).parent
A=json.loads((P/'analysis.json').read_text())
S={}; X={}
for batch in range(1,5):
    rows=list(csv.DictReader((P/f'sample_{batch}.csv').open()))
    out=[json.loads(line) for line in (P/f'answers_{batch}.jsonl').open()]
    assert len(rows)==len(out)==(40 if batch==4 else 100)
    assert {r['EVENT_ID'] for r in rows}=={r['id'] for r in out}
    assert len({r['id'] for r in out})==len(out) and all(r['status']=='ok' for r in out)
    for r in rows: S[r['EVENT_ID']]=r
    for r in out:
        text=re.sub(r'^```(?:json)?\s*|\s*```$','',r['response'].strip(),flags=re.I)
        X[r['id']]=json.loads(text)
assert len(S)==len(X)==340
D=collections.defaultdict(lambda:collections.Counter())
C=collections.Counter()
for id,r in S.items():
    a=X[id]; kind='s1' if r['s1_overlap']=='1' or id in {x['EVENT_ID'] for x in csv.DictReader((P/'sample_4.csv').open())} else r['hazard']
    c=D[kind];t=r['MAGNITUDE_TYPE'];v=a.get('wind_speed_value'); src=a.get('wind_speed_source') or 'none'
    joined=src
    if src in ('none','estimated_unspecified') and t in ('MG','MS'):joined='measured'
    elif src=='none' and t in ('EG','ES') and r['MAGNITUDE']:joined='estimated_unspecified'
    c['n']+=1;c['narrative_numeric']+=v is not None;c['structured_numeric']+=bool(r['MAGNITUDE']);c['speed_n']+=bool(r['MAGNITUDE']) or v is not None
    c['src_'+joined]+=1
    if bool(r['MAGNITUDE']) or v is not None:c['speed_src_'+joined]+=1
    c['strict']+=joined in ('measured','radar');c['wide']+=joined in ('measured','radar','observer_estimate')
    if (r['MAGNITUDE'] or v is not None):
        c['speed_strict']+=joined in ('measured','radar');c['speed_wide']+=joined in ('measured','radar','observer_estimate')
    if t=='EG':
        c['EG']+=1;c['EG_explicit_basis']+=src in ('measured','radar','damage_inferred','observer_estimate');c['EG_damage']+=src=='damage_inferred'
    if t in ('MG','MS','EG','ES'):C[(kind,t,joined)]+=1
    if r['MAGNITUDE'] and a.get('wind_speed_value') is not None:
        try:
            kt=float(r['MAGNITUDE']);mph=float(v)*(1 if a.get('wind_speed_unit')=='mph' else 1.15077945)
            c['both_speed']+=1;c['speed_within_5mph']+=abs(kt*1.15077945-mph)<=5
        except (ValueError,TypeError):pass
print('STRATA')
for k,c in D.items():
    print(k,dict(c))
print('TYPE JOINED')
for k,n in sorted(C.items()):print(k,n)
print('GOLD PARTIAL TYPE')
gold={x['event_id']:x for x in map(json.loads,(P/'gold_60.jsonl').open())}
for h in ['thunderstorm','tropical','synoptic']:
    ids=[i for i,g in gold.items() if g['hazard']==h]
    exact=sum(set(gold[i]['structure_type'])==set(X[i].get('structure_type') or []) for i in ids)
    overlap=sum(bool(set(gold[i]['structure_type'])&set(X[i].get('structure_type') or [])) or (not gold[i]['structure_type'] and not X[i].get('structure_type')) for i in ids)
    print(h,exact,overlap,len(ids),'gold_speed_present',sum(gold[i]['wind_speed_value'] is not None for i in ids),'gold_non_none_source',collections.Counter(gold[i]['wind_speed_source'] for i in ids))
print('SCORING CAUTION quote just literal substring, site is exact surface string, not canonical equivalence')
