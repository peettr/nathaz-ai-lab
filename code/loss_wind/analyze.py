#!/usr/bin/env python3
"""Score Gemini against independently transcribed 60-event gold, and audit all batches."""
import csv,json,re,random,pathlib,collections,math
P=pathlib.Path(__file__).parent
rows={r['EVENT_ID']:r for i in range(1,4) for r in csv.DictReader(open(P/f'sample_{i}.csv'))}
gold={r['event_id']:r for r in map(json.loads,open(P/'gold_60.jsonl'))}
def answer(text):
 text=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip(),flags=re.I)
 try:return json.loads(text)
 except Exception:
  m=re.search(r'\{.*\}',text,re.S)
  try:return json.loads(m.group()) if m else None
  except Exception:return None
pred={};invalid=[];status=collections.Counter()
for i in range(1,4):
 f=P/f'answers_{i}.jsonl'
 if not f.exists():continue
 for line in f.open():
  x=json.loads(line);status[x.get('status')]+=1
  if x.get('status')=='ok' or x.get('status')=='success':
   obj=answer(x.get('response',''))
   if isinstance(obj,dict):pred[str(x['id'])]=obj
   else:invalid.append(x['id'])
metric=collections.defaultdict(lambda:[0,0]); semantic_site=collections.defaultdict(lambda:[0,0]); confusion=collections.Counter(); examples=collections.defaultdict(list)
fields=['structure_type','damage_severity','wind_speed_value','wind_speed_kind','wind_speed_source','instrument_or_site','ef_damage_rating','damage_description','wind_speed_source_quote']
def norm(x):return str(x or '').strip().lower()
MPS={'mph':0.44704,'kt':0.514444,'kts':0.514444,'knots':0.514444,'m/s':1.0}
def as_mps(value,unit):
 try:return float(value)*MPS[norm(unit)]
 except (TypeError,ValueError,KeyError):return None
def site_semantic(a,b):
 a,b=norm(a),norm(b)
 return a==b or bool(a and b and (a in b or b in a))
def speed_eq(a,b):
 if a is None and b is None:return True
 try:return abs(float(a)-float(b))<.15
 except Exception:return False
for id,g in gold.items():
 if id not in pred:continue
 a=pred[id];haz=g['hazard']
 for field in fields:
  if field=='structure_type':correct=set(a.get(field) or [])==set(g[field])
  elif field=='wind_speed_value':
   v=a.get(field);u=a.get('wind_speed_unit');gv=g[field]
   vm=as_mps(v,u); gu=g.get('wind_speed_unit')
   lo=as_mps(g.get('wind_speed_lower'),gu);hi=as_mps(g.get('wind_speed_upper'),gu)
   gm=as_mps(gv,gu)
   correct=(gv is None and v is None) or (vm is not None and gm is not None and (lo-.5<=vm<=hi+.5 if lo is not None and hi is not None else abs(vm-gm)<=.5))
  elif field in ('damage_description','wind_speed_source_quote'):
   # Valid evidence quote rather than exact span: both empty, or literal substring of narrative.
   s=a.get(field) or ''; correct=(not s) if field=='wind_speed_source_quote' and g['wind_speed_source']=='none' else (bool(s) and s in rows[id]['EVENT_NARRATIVE'])
  else:correct=norm(a.get(field))==norm(g.get(field))
  metric[(haz,field)][1]+=1;metric[(haz,field)][0]+=int(correct)
  if field=='instrument_or_site':
   semantic_site[haz][1]+=1;semantic_site[haz][0]+=int(site_semantic(a.get(field),g.get(field)))
  if not correct and len(examples[(haz,field)])<5:examples[(haz,field)].append({'event_id':id,'gold':g.get(field),'model':a.get(field),'narrative':rows[id]['EVENT_NARRATIVE'][:700]})
 confusion[(g['wind_speed_source'],a.get('wind_speed_source','MISSING'))]+=1
ratio=collections.defaultdict(lambda:collections.Counter()); agreement=collections.Counter(); disagreements=[]
for id,a in pred.items():
 r=rows[id];haz=r['hazard']; t=r['MAGNITUDE_TYPE']; src=a.get('wind_speed_source','none')
 if src not in ('measured','radar','damage_inferred','observer_estimate','estimated_unspecified','none'):src='invalid'
 joined=src
 if src in ('none','estimated_unspecified') and t in ('MG','MS'):joined='measured'
 elif src=='none' and t in ('EG','ES') and r['MAGNITUDE']:joined='estimated_unspecified'
 ratio[haz][joined]+=1;ratio[haz]['n']+=1
 if a.get('wind_speed_value') is not None:ratio[haz]['narrative_speed_n']+=1
 if r['MAGNITUDE']:ratio[haz]['structured_speed_n']+=1
 if t=='EG':
  ratio[haz]['EG_n']+=1
  if src in ('damage_inferred','radar','observer_estimate','measured'):ratio[haz]['EG_basis_explicit_n']+=1
  if src=='damage_inferred':ratio[haz]['EG_damage_basis_n']+=1
 if r['MAGNITUDE'] or a.get('wind_speed_value') is not None:ratio[haz]['speed_n']+=1;ratio[haz]['speed_'+joined]+=1
 if t in ('MG','MS','EG','ES'):
  agreement[(t,joined)]+=1
  if t in ('MG','MS') and src in ('damage_inferred','observer_estimate','radar'):disagreements.append((id,t,src))
for i in range(1,4):
 ids=[r['EVENT_ID'] for r in list(rows.values())[(i-1)*100:i*100]]
 rng=random.Random(20261014+i); (P/f'claude_review_ids_{i}.json').write_text(json.dumps(rng.sample(ids,10),indent=2)+'\n')
report={'n_sample':len(rows),'n_pred':len(pred),'output_status':dict(status),'invalid_json':invalid,'gold_scored':len(set(pred)&set(gold)),'field_metric':{h+'|'+f:{'correct':v[0],'total':v[1],'accuracy':round(v[0]/v[1],3)} for (h,f),v in metric.items()},'site_semantic_metric':{h:{'correct':v[0],'total':v[1],'accuracy':round(v[0]/v[1],3)} for h,v in semantic_site.items()},'source_confusion':{g+'|'+p:n for (g,p),n in confusion.items()},'source_counts':{h:dict(v) for h,v in ratio.items()},'magnitude_type_by_joined':{t+'|'+s:n for (t,s),n in agreement.items()},'metadata_conflict':disagreements,'failure_examples':{h+'|'+f:v for (h,f),v in examples.items()}}
(P/'analysis_r1b.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('pred',len(pred),'gold',report['gold_scored'],'invalid',len(invalid),'statuses',status)
