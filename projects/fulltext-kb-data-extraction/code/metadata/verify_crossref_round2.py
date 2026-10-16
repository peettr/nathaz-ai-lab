#!/usr/bin/env python3
"""DOI-only Crossref verification; resumable, never sends local titles."""
import csv, difflib, json, re, sqlite3, time, unicodedata, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZOTERO = './ftkb/zotero.sqlite'
UA = 'LabMetadataVerifier/1.0 (mailto:[邮箱])'
MAILTO = '[邮箱]'
LOG = HERE / 'crossref_responses.jsonl'
DOI_RE = re.compile(r'^10\.\d{4,9}/\S+$', re.I)

def read_csv(name):
    with (HERE/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def clean_doi(value):
    value = (value or '').strip().lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)', '', value)
    return value.rstrip('.,; ')

def norm(s):
    s = unicodedata.normalize('NFKC', s or '').casefold()
    return ''.join(c for c in s if c.isalnum())

def similarity(a,b):
    if not a or not b: return None
    return round(difflib.SequenceMatcher(None,norm(a),norm(b),autojunk=False).ratio(),4)

def year_from(m):
    for key in ('published','published-print','published-online','issued','created'):
        try: return str(m[key]['date-parts'][0][0])
        except (KeyError, IndexError, TypeError): pass
    return ''

def fetch(doi):
    if not DOI_RE.match(doi) or any(ch.isspace() for ch in doi):
        return {'state':'invalid_candidate'}
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='') + '?mailto=' + urllib.parse.quote(MAILTO)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=25) as r:
                m = json.load(r)['message']
            authors = m.get('author') or []
            first = authors[0] if authors else {}
            return {'state':'exists','resolved_doi':m.get('DOI',''),
                    'title':(m.get('title') or [''])[0],
                    'first_author':' '.join(filter(None,[first.get('given',''),first.get('family','')])),
                    'year':year_from(m),'container':(m.get('container-title') or [''])[0],
                    'type':m.get('type','')}
        except urllib.error.HTTPError as e:
            if e.code == 404: return {'state':'not_found'}
            if e.code not in (408,429,500,502,503,504):
                return {'state':'http_error_'+str(e.code)}
            if attempt == 2: return {'state':'http_error_'+str(e.code)}
            time.sleep(2**attempt + (float(e.headers.get('Retry-After','0')) if e.headers.get('Retry-After','0').isdigit() else 0))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as e:
            if attempt == 2: return {'state':'error_'+type(e).__name__}
            time.sleep(2**attempt)
    return {'state':'error_unknown'}

def write_csv(name, rows, fields):
    with (HERE/name).open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader();w.writerows(rows)

def zotero_dois():
    c=sqlite3.connect('file:'+ZOTERO+'?mode=ro',uri=True)
    q='''SELECT i.key, v.value FROM itemData d JOIN itemDataValues v ON d.valueID=v.valueID
         JOIN items i ON i.itemID=d.itemID WHERE d.fieldID=(SELECT fieldID FROM fields WHERE fieldName='DOI')'''
    z=defaultdict(set)
    for key,value in c.execute(q):
        doi=clean_doi(value)
        if doi: z[doi].add(key)
    c.close()
    return z

def main():
    desktop=read_csv('desktop_records.csv'); endnote=read_csv('endnote_records.csv')
    sources=defaultdict(list)
    for source,rows in [('desktop',desktop),('endnote',endnote)]:
        for i,row in enumerate(rows):
            doi=clean_doi(row['doi'])
            if doi: sources[doi].append((source,i,row))
    done={}
    if LOG.exists():
        with LOG.open(encoding='utf-8') as f:
            for line in f:
                x=json.loads(line);done[x['doi']]=x['response']
    pending=sorted(set(sources)-set(done)); print('unique',len(sources),'cached',len(done),'pending',len(pending),flush=True)
    last=0
    with LOG.open('a',encoding='utf-8') as f:
        for j,doi in enumerate(pending,1):
            wait=max(0,0.21-(time.monotonic()-last))
            if wait:time.sleep(wait)
            last=time.monotonic()
            result=fetch(doi)
            done[doi]=result
            f.write(json.dumps({'doi':doi,'response':result},ensure_ascii=False)+'\n');f.flush()
            if j%100==0:print('queried',j,'/',len(pending),'last',doi,result['state'],flush=True)
    z=zotero_dois()
    out=[]
    for doi,entries in sorted(sources.items()):
        m=done[doi]; status=m['state']; title=m.get('title','')
        for source,i,row in entries:
            sim=similarity(title,row['title']) if status=='exists' else None
            # Very short/generic filename candidates must not be trusted solely on ratio.
            consistent=(sim is not None and sim>=0.82 and len(norm(row['title']))>=25)
            judgement=('一致' if consistent else '疑似误抓') if status=='exists' else ('不存在' if status=='not_found' else '未核实')
            out.append({'doi':doi,'source':source,'source_id':row['sha256'] if source=='desktop' else row['record_id'],
                'candidate_title':row['title'],'exists': 'yes' if status=='exists' else ('no' if status=='not_found' else 'unknown'),
                'crossref_doi':m.get('resolved_doi',''),'crossref_title':title,
                'crossref_first_author':m.get('first_author',''),'crossref_year':m.get('year',''),
                'crossref_container':m.get('container',''),'crossref_type':m.get('type',''),
                'title_similarity':sim if sim is not None else '', 'judgement':judgement,'lookup_state':status,
                'zotero_keys_same_doi':';'.join(sorted(z.get(doi,set()))),
                'year_disagrees': 'yes' if row['year'][:4].isdigit() and m.get('year','')[:4].isdigit() and abs(int(row['year'][:4])-int(m['year'][:4]))>1 else 'no'})
            if consistent:
                row['title']=title; row['authors']=m.get('first_author','') or row['authors'];row['year']=m.get('year','') or row['year']
                row['title_source']='crossref';row['metadata_confidence']='crossref_doi_and_title_verified' if source=='endnote' else row['confidence']
                if source=='desktop':row['confidence']='high_crossref_match'
    fields=list(out[0]);write_csv('doi_verified.csv',out,fields)
    for name,rows,original in [('desktop_records_v2.csv',desktop,'desktop_records.csv'),('endnote_records_v2.csv',endnote,'endnote_records.csv')]:
        for row in rows: row.setdefault('title_source','original')
        write_csv(name,rows,list(read_csv(original)[0])+['title_source'])
    from collections import Counter
    counts=Counter(x['judgement'] for x in out); unique=Counter(done[d]['state'] for d in sources)
    cross=[x for x in out if x['zotero_keys_same_doi']]
    unmatched=[d for d in sources if done[d]['state'] not in ('exists','not_found')]
    report=f'''# Crossref DOI 候选核实（第二轮 A）\n\n只将 DOI 字符串送至 Crossref Works API；请求 User-Agent 带 mailto、间隔至少 0.21 秒，每个可重试错误最多重试 2 次。源 CSV、Zotero 复制库只读。Crossref 响应本地日志 `{LOG.name}` 可断点续查。\n\n候选记录：台式机 {sum(bool(r['doi']) for r in read_csv('desktop_records.csv'))}、EndNote {sum(bool(r['doi']) for r in read_csv('endnote_records.csv'))}；独立 DOI 字符串 {len(sources)}。独立 DOI 查到记录 {unique['exists']}、404 {unique['not_found']}、未核实/格式异常 {sum(v for k,v in unique.items() if k not in ('exists','not_found'))}。按每条来源记录判定：{dict(counts)}。\n\n判定：题名 NFKC、大小写折叠、去标点空格后用 SequenceMatcher 算相似度；相似度 ≥0.82 且本地题名至少 25 个字母数字，才列“一致”并在 v2 回填 Crossref 题名、第一作者、年份及高置信度标记；其余有效 DOI 虽可解析，仍列“疑似误抓”，不回填。`year_disagrees` 独立提示相差超过 1 年；“一致”可能仍有同 DOI 引用条目、不同版本或早发/刊年问题，应人工核原 PDF。非 404 的网络/格式问题一律“未核实”，不可当不存在。\n\n与 Zotero 元数据中 DOI 字符串精确求交（不传 Zotero 条目到外部服务）：命中 DOI {len(set(x['doi'] for x in cross))} 个、台式机/EndNote 来源记录 {len(cross)} 条、来源记录—Zotero 条目对子 {sum(len(x['zotero_keys_same_doi'].split(';')) for x in cross)} 对；其中“一致”来源记录 {sum(x['judgement']=='一致' for x in cross)} 条。这是 DOI 相同的候选对子数，不等于 PDF 已去重。\n\n输出 `doi_verified.csv` 每条 DOI 来源候选一行，含 Crossref 实际 DOI、书目信息、题名相似度、判定和 Zotero key；`desktop_records_v2.csv` 与 `endnote_records_v2.csv` 未覆盖旧文件。需单独复核的查询状态：{len(unmatched)} 个 DOI；实际取值详见 `doi_verified.csv`。\n\nCrossref API：https://api.crossref.org/works/ （逐 DOI 查询；不代表出版社全文核验）。\n'''
    (HERE/'README_round2.md').write_text(report,encoding='utf-8')
    print('done',len(out),dict(counts),dict(unique),'zotero_pairs',sum(len(x['zotero_keys_same_doi'].split(';')) for x in cross),flush=True)
if __name__=='__main__': main()
