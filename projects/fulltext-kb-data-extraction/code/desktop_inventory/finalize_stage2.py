#!/usr/bin/env python3
"""Lightweight read-only corpus accounting and packed manifest exports; no OCR."""
import collections, gzip, json, pathlib, random, sqlite3, os, shutil, time
R=pathlib.Path('./ftkb_desktop'); DB=R/'page_text.sqlite'; HERE=pathlib.Path(__file__).resolve().parent
con=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
C=collections.Counter(); bydir=collections.defaultdict(collections.Counter); candidates=collections.Counter(); samples=collections.defaultdict(list)
def group(path):
    pp=path.split('/')
    if path.startswith('./Book/'): return 'Book/'+(pp[4] if len(pp)>4 else '(root)')
    if path.startswith('./Literature/'): return 'Literature/'+(pp[4] if len(pp)>4 else '(root)')
    return '(other)'
for line in (R/'stage2_no_text_pages.jsonl').open():
    x=json.loads(line); candidates[(x['sha256'],x['physical_page'])]+=1
    bydir[group(x['aliases'][0]['wsl'])]['target']+=1
out=R/'page_manifest_packed.jsonl'; gz=R/'page_manifest_packed_full.jsonl.gz'; aliasout=R/'page_manifest_packed_aliases.jsonl'
# The per-page compact file references document aliases by SHA; the full per-page
# alias-bearing manifest is gzip compressed, to keep new writes well below 200 MB.
with aliasout.open('w') as a:
    for h,als in con.execute('select sha256,aliases_json from documents order by sha256'):
        a.write(json.dumps({'sha256':h,'aliases':json.loads(als)},ensure_ascii=False,separators=(',',':'))+'\n')
with out.open('w') as f, gzip.open(gz,'wt',encoding='utf8',compresslevel=6) as z:
    for h,p,chars,present,origin,als,text in con.execute('select p.sha256,p.physical_page,p.chars,p.has_text,p.origin,d.aliases_json,p.text from pages p join documents d on p.sha256=d.sha256 order by p.sha256,p.physical_page'):
        aliases=json.loads(als); g=group(aliases[0]['wsl']); key=(h,p)
        if origin=='OCR 文本':
            C['ocr']+=1; C['ocr_text']+=present; bydir[g]['done']+=1
            if len(samples[g])<200:
                samples[g].append((h,p,text,aliases[0]['wsl']))
        if origin=='OCR 文本' and key in candidates: C['target_seen']+=1
        C['pages']+=1; C['text']+=present
        row={'sha256':h,'physical_page':p,'characters':chars,'has_text':bool(present),'origin':origin,'sqlite_row':{'table':'pages','sha256':h,'physical_page':p},'aliases_ref':h}
        f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
        full={**row,'aliases':aliases,'db_path':str(DB)}
        z.write(json.dumps(full,ensure_ascii=False,separators=(',',':'))+'\n')
assert C['ocr']==C['target_seen'] and C['ocr']==sum(v['done'] for v in bydir.values())
C['target']=sum(candidates.values()); C['remaining']=C['target']-C['ocr']
for g,v in bydir.items():v['remaining']=v['target']-v['done']
# 20-page textual inspection: sample distinct docs, with Chinese filename preferentially included.
ocr=[]
for g,group_samples in samples.items():ocr.extend((g,*x) for x in group_samples)
rng=random.Random(20261015);rng.shuffle(ocr); selected=[]; seen=set()
for wanted in (True,False):
    for g,h,p,text,path in ocr:
        if (any('\u3400'<=ch<='\u9fff' for ch in path)!=wanted or h in seen or not text):continue
        selected.append({'group':g,'sha256':h,'page':p,'path':path,'characters':len(text),'excerpt':text[:950].replace('\n',' ')})
        seen.add(h)
        if len(selected)>= (10 if wanted else 20):break
# if fewer than 20 distinct docs in sampled subset, fill across pages.
for g,h,p,text,path in ocr:
    if len(selected)>=20:break
    if text and not any(x['sha256']==h and x['page']==p for x in selected):selected.append({'group':g,'sha256':h,'page':p,'path':path,'characters':len(text),'excerpt':text[:950].replace('\n',' ')})
print(json.dumps({'counts':C,'bydir':bydir,'files':{p.name:p.stat().st_size for p in (out,gz,aliasout,DB)},'samples':selected},ensure_ascii=False,indent=2))
