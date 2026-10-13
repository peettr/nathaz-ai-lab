"""Score frozen r2 output. Does not change items or raw answers."""
import json,re,math,collections,statistics
from pathlib import Path
p=Path(__file__).parent;items={x['id']:x for x in map(json.loads,(p/'eval_set_r2.jsonl').read_text().splitlines())}
def parse(s):
 if isinstance(s,dict):return s
 s=str(s).replace('```json','').replace('```','')
 try:return json.loads(re.search(r'\{[^{}]*\}',s,re.S).group())
 except Exception:return {}
def correct(x,s):
 a=parse(s).get('answer')
 if x['group']!='B2':return str(a).strip()==x['answer']
 try:v=float(re.search(r'[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?',str(a).replace(',','')).group())
 except Exception:return False
 u=str(parse(s).get('unit','')).strip().lower().replace(' ','').replace('³','3').replace('²','2').replace('percent','%')
 wanted=str(x['unit']).lower().replace(' ','')
 aliases={'1':{'1','dimensionless','none','unitless','ratio','-','','mach'},'D':{'d','1','dimensionless','unitless'},'%':{'%','percent'},'kg/m3':{'kg/m3','kgm-3','kg/m^3'},'m/s':{'m/s','ms-1','m·s-1'},'million cells':{'millioncells','millionsofcells','million','millions'},'1:denominator':{'1:denominator','1','denominator','none','unitless'},'taps':{'taps','pressuretaps'},'s':{'s','seconds','second'},'CPU h':{'cpuh','cpuhours','h','hours'},'directions':{'directions','winddirections'},'positions':{'positions','interferingpositions'},'conditions':{'conditions','experimentalconditions'}}
 valid=u==wanted or u in aliases.get(x['unit'],set()) or (x['unit']=='1:denominator' and u==f'1:{int(x["answer"])}scale(denominator)')
 # Original B items include count units (taps, faces, layers, etc.): require explicit.
 return valid and abs(v-float(x['answer']))<=.01*max(abs(float(x['answer'])),1e-10)
def wilson(k,n):
 if not n:return [None,None]
 z=1.95996398454;mid=(k+z*z/2)/(n+z*z);radius=z*math.sqrt(k*(n-k)/n+z*z/4)/ (n+z*z)
 return [round(mid-radius,4),round(mid+radius,4)]
def read_rows(filename):
 out={}
 for s in (p/filename).read_text().splitlines():
  x=json.loads(s)
  if x['id'] in items and not x.get('error') and x.get('status','ok')=='ok':out[x['id']]=x
 return out
models={}
for name,file,shape in [('Claude Sonnet','claude_answers_r2.jsonl','lines'),('Gemini 3.8 Flash high','gemini_answers_r2.jsonl','lines'),('Qwen3-30B-A3B-FP8','30b_answers_r2.json','obj'),('Qwen3-32B-AWQ','32b_answers_r2.json','obj')]:
 if not (p/file).exists():continue
 if shape=='lines':responses=read_rows(file);meta={}
 else:
  meta=json.loads((p/file).read_text());responses={r['id']:r for r in meta['rows']}
 results=[]
 for group in ('A2','B2','C2'):
  cohort=[x for x in items.values() if x['group']==group];valid=[x for x in cohort if x['id'] in responses];hits=sum(correct(x,responses[x['id']].get('response','')) for x in valid)
  v={'group':group,'n':len(cohort),'answered':len(valid),'correct':hits,'accuracy':round(hits/len(cohort),4),'ci95':wilson(hits,len(cohort))}
  if group=='A2':
   tp=sum(correct(x,responses[x['id']].get('response','')) for x in valid if x['answer']=='是')
   pred=sum(parse(responses[x['id']].get('response','')).get('answer')=='是' for x in valid)
   v.update(tp=tp,pred_positive=pred,recall=round(tp/50,4),recall_ci95=wilson(tp,50),precision=round(tp/pred,4) if pred else 0,precision_ci95=wilson(tp,pred))
  subset=[responses[x['id']] for x in valid]
  if name.startswith('Claude'):
   v.update(input_tokens=[已隐去]'usage',{}).get('input_tokens',0)+y.get('usage',{}).get('cache_creation_input_tokens',0)+y.get('usage',{}).get('cache_read_input_tokens',0) for y in subset),output_tokens=[已隐去]'usage',{}).get('output_tokens',0) for y in subset),cli_net_input_tokens=[已隐去]'usage',{}).get('input_tokens',0) for y in subset),usd=sum(y.get('cost_usd') or 0 for y in subset))
  elif name.startswith('Gemini'):
   v.update(input_tokens=[已隐去]'usage',{}).get('input_tokens',0) for y in subset),output_tokens=[已隐去]'usage',{}).get('output_tokens',0) for y in subset),total_tokens=[已隐去]'usage',{}).get('total_tokens',0) for y in subset),subscription_usd=None)
  else:v.update(input_tokens=[已隐去]'input_tokens'] for y in subset),output_tokens=[已隐去]'output_tokens'] for y in subset))
  results.append(v)
 models[name]={'results':results,'meta':{k:meta[k] for k in ('model','elapsed_s') if k in meta},'count':len(responses)}
# Keyword-only rules are frozen in freeze_eval_r2.py.
def kwA(x):return '是' if re.search(r'downburst|microburst|thunderstorm|outflow|gust front',x['prompt'].split('摘要：',1)[1],re.I) else '否'
def kwC(x):return 'Thunderstorm Wind' if re.search(r'\b(thunderstorm|tstm|t-storm|convective|squall line|downburst|microburst|supercell|outflow boundary|storm cell)\b',x['prompt'].split('叙述：',1)[1],re.I) else '非对流性大风'
base={g:sum(f(x)==x['answer'] for x in items.values() if x['group']==g) for g,f in [('A2',kwA),('C2',kwC)]}
(p/'scores_r2.json').write_text(json.dumps({'models':models,'baseline':base,'items':len(items)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'models':models,'baseline':base},ensure_ascii=False,indent=2))
