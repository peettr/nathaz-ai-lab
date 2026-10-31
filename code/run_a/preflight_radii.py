import csv,collections,datetime
r=collections.defaultdict(list)
for x in csv.DictReader(open('/content/a_inputs_v2/tracks.csv')):r[x['event']].append(x)
for e,rows in sorted(r.items()):
 invalid=[]
 for x in rows:
  v=float(x['vmax_kt']);valid=[]
  for k in (34,50,64):
   if v<=k:continue
   n=sum(float(x[f'r{k}_{q}_nmi'])>0 for q in ('ne','se','sw','nw'))
   if n>=2:valid.append(k)
  if len(valid)<2:invalid.append((x['time_utc'],valid))
 print(e,len(rows),'invalid_nodes',invalid,flush=True)
