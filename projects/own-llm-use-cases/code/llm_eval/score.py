import json,re,math,collections,sys
from pathlib import Path
ROOT=Path(__file__).parent; items={j['id']:j for j in map(json.loads,(ROOT/'eval_set.jsonl').read_text().splitlines())}
def parsed(text):
 text=re.sub(r'<think>[\s\S]*?</think>','',text)
 try:return json.loads(re.search(r'\{[^{}]*\}',text).group())
 except Exception:return None
def correct(item,pred):
 if not isinstance(pred,dict) or 'answer' not in pred:return False
 if item['group'] in 'BD':
  try:
   s=str(pred['answer']).replace(',','');m=re.search(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',s);v=float(m.group())
   numeric=abs(v-float(item['answer']))<=0.01*abs(float(item['answer']))
   if item['group']=='B':
    raw=str(pred.get('unit','')).lower().replace('³','3').replace('²','2').replace('hours','h').replace('hour','h').replace('seconds','s').replace('second','s')
    u=re.sub(r'[^a-z0-9]','',raw); expected=re.sub(r'[^a-z0-9]','',item['unit'].lower())
    alias={'taps':['taps','pressuretaps'],'cpuh':['cpuh','cpuhours'],'directions':['directions','winddirections'],'1denominator':['1denominator','1400geometricscaleratiodenominator','1'],'conditions':['conditions','experimentalconditions'],'millioncells':['millioncells','million','milliongridcells','millionsofcells','m']}
    if expected=='1' and ('dimensionless' in u or u in ['','unitless','ratio','none','iu','mach']):return numeric
    return numeric and (u==expected or u in alias.get(expected,[]))
   return numeric
  except:return False
 return str(pred['answer']).strip().lower()==str(item['answer']).strip().lower()
def baseline(item):
 t=item['prompt'].lower()
 if item['group']=='A':return '是' if re.search('downburst|thunderstorm|microburst|downdraft',t.split('摘要：')[0]) else '否'
 if item['group']=='C':
  t=t.split('描述：')[-1]
  if re.search('tstm|thunderstorm|convective|squall line',t):return 'Thunderstorm Wind'
  if re.search('strong winds?',t):return 'Strong Wind'
  if re.search('high winds?|non.thunderstorm|gradient winds?',t):return 'High Wind'
  return '其他'
 return None
def summary(model,rows):
 o=[]
 for g in 'ABCD':
  xs=[x for x in items.values() if x['group']==g];res={x['id']:x for x in rows}
  attempts=[x for x in xs if x['id'] in res];right=sum(correct(x,parsed(res[x['id']].get('response',''))) for x in attempts)
  z={'group':g,'model':model,'n':len(xs),'attempts':len(attempts),'correct':right,'score':right/len(xs),'input_tokens':sum(r.get('input_tokens',r.get('usage',{}).get('input_tokens',0)+r.get('usage',{}).get('cache_creation_input_tokens',0)+r.get('usage',{}).get('cache_read_input_tokens',0)) for x in attempts if (r:=res[x['id']])), 'output_tokens':sum(r.get('output_tokens',r.get('usage',{}).get('output_tokens',0)) for x in attempts if (r:=res[x['id']])), 'cost_usd':sum(res[x['id']].get('cost_usd') or 0 for x in attempts)}
  if g=='A':
   TP=sum(x['answer']=='是' and (parsed(res.get(x['id'],{}).get('response','')) or {}).get('answer')=='是' for x in xs);FP=sum(x['answer']=='否' and (parsed(res.get(x['id'],{}).get('response','')) or {}).get('answer')=='是' for x in xs)
   z.update(recall=TP/10,precision=TP/(TP+FP) if TP+FP else 0,TP=TP,FP=FP)
  o.append(z)
 return o
if __name__=='__main__':
 models={'keyword':[{**x,'response':json.dumps({'answer':baseline(x)},ensure_ascii=False)} for x in items.values() if x['group'] in 'AC']}
 p=ROOT/'claude_responses.jsonl'
 if p.exists():models['Claude Sonnet']=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
 for m in ('8b','30b'):
  p=ROOT/(m+'_responses.json')
  if p.exists():models[m]=json.loads(p.read_text())['rows']
 print(json.dumps([r for model,rows in models.items() for r in summary(model,rows)],ensure_ascii=False,indent=2))
