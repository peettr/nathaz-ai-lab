#!/usr/bin/env python3
"""Select unique PDF representatives and stratified inspection sample."""
import json,random,re,collections
from pathlib import Path
R=Path(__file__).parent
allpdf=[json.loads(s) for s in (R/'remote_metadata.jsonl').open() if '".pdf"' in s]
hashes={x['path']:x['sha256'] for s in (R/'remote_hashes.jsonl').open() if (x:=json.loads(s)).get('sha256')}
by=collections.defaultdict(list)
for x in allpdf:by[hashes.get(x['path'],x['path'])].append(x)
reps=[]
for files in by.values():
    x=min(files,key=lambda y:y['path']);x['aliases']=[y['path'] for y in files];reps.append(x)
random.seed(20261014)
strata=collections.defaultdict(list)
for x in reps:
    cat='Book' if x['path'].startswith('./Book/') else 'Literature'
    lang='CJKname' if re.search('[\u3400-\u9fff]',x['path'].split('/')[-1]) else 'other'
    strata[(cat,lang)].append(x)
# At least 100 Book and 60 CJK filename documents, plus broad random representatives.
samples=set()
for k,items in strata.items():
    n=min(len(items), 100 if k[0]=='Book' else 120 if k[1]=='CJKname' else 360)
    samples.update(y['path'] for y in random.sample(items,n))
for x in reps:x['sample_text']=x['path'] in samples
(R/'remote_pdf_representatives.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in reps))
print('unique',len(reps),'sample',len(samples),'strata',[(str(k),len(v),sum(z['path'] in samples for z in v)) for k,v in strata.items()])
