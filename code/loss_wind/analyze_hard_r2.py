#!/usr/bin/env python3
"""Hard-case source audit; no reinterpretation of MAGNITUDE_TYPE as narrative ground truth."""
import pathlib,json,collections,re
P=pathlib.Path(__file__).parent
G={x['event_id']:x for x in map(json.loads,(P/'gold_hard_70.jsonl').open())}
R={x['EVENT_ID']:x for x in __import__('csv').DictReader((P/'sample_hard_70_v2.csv').open())}
A={};statuses=collections.Counter();invalid=[]
for line in (P/'answers_hard_70.jsonl').open():
 x=json.loads(line);statuses[x.get('status')]+=1
 if x.get('status')!='ok':continue
 try:
  text=re.sub(r'^```(?:json)?\s*|\s*```$','',x['response'].strip(),flags=re.I)
  a=json.loads(text);assert isinstance(a,dict)
  A[x['id']]=a
 except (ValueError,KeyError,AssertionError):invalid.append(x['id'])
conf=collections.Counter((g['primary_source'],A[id].get('primary_source','MISSING')) for id,g in G.items() if id in A)
classes=['none','estimated_unspecified','measured','damage_inferred','radar','observer_estimate']
metrics={}
for c in classes:
 tp=conf[c,c]; n_g=sum(n for (g,p),n in conf.items() if g==c);n_p=sum(n for (g,p),n in conf.items() if p==c)
 metrics[c]={'gold':n_g,'predicted':n_p,'tp':tp,'precision':round(tp/n_p,3) if n_p else None,'recall':round(tp/n_g,3) if n_g else None}
errors=[{'id':id,'gold':g['primary_source'],'prediction':A[id].get('primary_source'),'narrative':R[id]['EVENT_NARRATIVE'][:500]} for id,g in G.items() if id in A and A[id].get('primary_source')!=g['primary_source']]
multivalue={}
for id in ['977217','787346','1051086','1141750','1010706','732458','1000842','994189']:
 if id in A:multivalue[id]={'returned':A[id].get('wind_observations'),'n_returned':len(A[id].get('wind_observations') or [])}
report={'gold_n':len(G),'parsed_n':len(A),'status':dict(statuses),'invalid':invalid,'confusion':{g+'|'+p:n for (g,p),n in conf.items()},'per_class':metrics,'errors':errors,'multi_case_audit':multivalue}
(P/'analysis_hard_r2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('parsed',len(A),'statuses',statuses,'errors',len(errors));print(metrics)
