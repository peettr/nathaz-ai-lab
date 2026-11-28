#!/usr/bin/env python3
"""Read-only, heuristic parser of legacy EndNote MyISAM dynamic rows."""
import csv, re, struct, unicodedata, difflib
from pathlib import Path
from collections import Counter, defaultdict
BASE=Path(__file__).parent
B=(BASE/'refs.MYD').read_bytes()
YEAR=re.compile(rb'\x04\x00\x00((?:18|19|20)\d\d)')
# The dynamic-row prefix contains a little-endian 32-bit record id, followed by
# 24-bit author length, author bytes, 24-bit year length and year bytes.
def u24(b): return int.from_bytes(b,'little')
def text(b): return b.decode('utf-8','replace').strip('\x00\r\n ')
def prefix_at(yearpos):
    for p in range(yearpos-7,max(-1,yearpos-4001),-1):
        if u24(B[p:p+3]) != yearpos-p-3: continue
        if p<5: continue
        au=B[p+3:yearpos]
        if not (3<=len(au)<4000 and sum(32<=c<=126 or c in (10,13) or c>=128 for c in au)/len(au)>.85): continue
        if 48<=B[p-5]<=63:
            rid=int.from_bytes(B[p-4:p],'little')
            if 0<rid<100000:return p,rid,text(au)
        # Rows with a text_styles blob before author have an additional length
        # and sometimes XML before the author field. Recover id from nearest marker.
        region=B[max(0,p-300):p]
        matches=list(re.finditer(rb'[0-?]([\x01-\xff]\x00\x00\x00)',region))
        if matches:
            rid=int.from_bytes(matches[-1].group(1),'little')
            if 0<rid<100000:return p,rid,text(au)
        return p,'offset-'+str(p),text(au)
    return None

def fields(start,end):
    # MYD strings in this schema have variable 1/2/3-byte length markers.
    # Parse first required title, pages and secondary_title by ordered length marker.
    p=start; out=[]
    while p<end:
        best=None
        for width in (3,2,1):
            if p+width>end: continue
            n=u24(B[p:p+width]); q=p+width+n
            if n>0 and n<20000 and q<=end:
                raw=B[p+width:q]
                printable=sum(32<=c<=126 or c in (9,10,13) or c>=128 for c in raw)/n
                if printable>.87 and (width!=3 or B[p+1:p+3]==b'\0\0'):
                    best=(q,text(raw));break
        if best:
            out.append(best[1]);p=best[0]
        else:p+=1
    return out

candidates=[]
for m in YEAR.finditer(B):
    z=prefix_at(m.start())
    if not z and m.start()==251705:
        # A row with empty author has a 2-byte null marker before year.
        z=(m.start()-16,406,'')
    if not z: continue
    p,rid,author=z
    t=m.end(); n=u24(B[t:t+3]); title=text(B[t+3:t+3+n]) if 5<n<700 and t+3+n<=len(B) else ''
    if not title:continue
    candidates.append((p,rid,author,m.group(1).decode(),title,t+3+n))
# unique record starts, not text's incidental year matches
unique={}
for c in candidates:unique.setdefault(c[0],c)
rows=[]; cs=sorted(unique.values())
for i,(p,rid,author,year,title,nextpos) in enumerate(cs):
    stop=cs[i+1][0] if i+1<len(cs) else len(B)
    # Subsequent fields follow title: pages, secondary_title, volume, number.
    vals=fields(nextpos,min(stop,nextpos+500))
    pages=vals[0] if vals and re.search(r'\d',vals[0]) and len(vals[0])<70 else ''
    journal=''
    for v in vals[:5]:
        if v!=pages and len(v)>4 and not v.lower().startswith(('http','internal-pdf')):
            journal=v;break
    volume=next((v for v in vals[1:6] if v.isdigit() and len(v)<5),'')
    raw=B[nextpos:stop]
    # Extract links and PDF-ish names from the remainder of the current row.
    pdfs=re.findall(rb'[^\x00-\x1f]{1,260}?\.pdf',raw,re.I)
    pdfs=[text(x) for x in pdfs]
    image=''; link=''
    for v in pdfs:
        if 'internal-pdf://' in v.lower():link=v[v.lower().index('internal-pdf://'):]
        elif re.search(r'\d{7,}[^/\\]*\.pdf$',v,re.I): image=v
    # If the 24-bit marker immediately precedes filename, strip it by tail match.
    if image:
        k=re.search(r'(\d{8,}[^/\\\x00-\x1f]*?\.pdf)$',image,re.I)
        if k:image=k.group(1)
    doi=''
    match=re.search(rb'10\.\d{4,9}/[^\x00\s<>]{2,140}',raw,re.I)
    if match:doi=text(match.group()).rstrip('.,;)')
    rows.append(dict(record_id=rid,author=author,year=year,title=title,journal=journal,volume=volume,pages=pages,doi=doi,image=image,link_to_pdf=link,raw_pdf_candidates=';'.join(pdfs),offset=p))

# A legacy text_styles blob may produce a plausible but wrong id; keep ids unique.
seen_ids=set()
for r in rows:
    if r['record_id'] in seen_ids:r['record_id']='offset-'+str(r['offset'])
    seen_ids.add(r['record_id'])

listing={}
for line in (BASE/'data_listing.tsv').read_text(encoding='utf-8-sig').splitlines():
    cols=line.split('\t')
    if len(cols)>1:listing[cols[0].replace('\\','/')]=cols[1]

def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).casefold())
def file_match(row):
    ims=[row['image'], row['link_to_pdf'].split('/')[-1]]
    choices=[]
    for j,q in enumerate(ims):
        if not q:continue
        q=q.split('\\')[-1].split('/')[-1]
        if q in listing:choices.append((1.0,q,'exact'))
        if 'PDF/'+q in listing:choices.append((1.0,'PDF/'+q,'exact'))
        # Prefix may be truncated: require uniquely matching remaining original tail.
        stem=re.sub(r'^\d{8,12}','',q,flags=re.I)
        if len(norm(stem))>=8:
            for f in listing:
                fn=f.split('/')[-1]
                if norm(fn).endswith(norm(stem)):
                    choices.append((.85,f,'tail'))
    if not choices:return '否','','none'
    choices.sort(reverse=True)
    best=choices[0]
    if len({x[1] for x in choices if x[0]==best[0]})>1:return '待核',';'.join(sorted({x[1] for x in choices if x[0]==best[0]})),'ambiguous'
    return '是',best[1],best[2]
for r in rows:
    r['has_file'],r['file_relpath'],r['match_confidence']=file_match(r)

with (BASE/'third_refs.csv').open('w',newline='',encoding='utf-8-sig') as f:
    cols=['record_id','author','year','title','journal','volume','pages','doi','image','link_to_pdf','has_file','file_relpath','match_confidence']
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r[k] for k in cols} for r in rows)
print('year anchors',len(list(YEAR.finditer(B))),'parsed',len(rows),'unique ids',len({r['record_id'] for r in rows}),'Kareem',sum(bool(re.search(r'\bkareem\b',r['author'],re.I)) for r in rows))
print('pdf match counts',Counter(r['match_confidence'] for r in rows))
print('first rows',[(r['record_id'],r['title'],r['journal'],r['image'],r['has_file']) for r in rows[:4]])
