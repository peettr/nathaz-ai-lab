"""Read archived Chrome department pages; do not fetch or guess missing cards."""
import csv, html, json, re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

root=Path(__file__).parent
snaps=root/'snapshots'
labels={'pre':'Pre-train','infra':'Infra','post':'Post-train','harness':'Agent Harness','physics':'Physics','optimization':'Optimization','quant':'Quant','bio':'Biology','medical':'Medicine','earth':'Earth & weather','materials':'Materials','astro':'Astronomy'}
rows={}
counts={}
for meta_path in sorted(snaps.glob('*.meta.json')):
    meta=json.loads(meta_path.read_text())
    params=parse_qs(urlparse(meta['url']).query)
    if '/live/challenges' not in meta['url'] or 'department' not in params:
        continue
    key=params['department'][0]
    if key not in labels: continue
    body=Path(meta['files']['html']).read_text()
    cards=re.findall(r'<article data-v-138bb890="">(.*?)</article>',body,re.S)
    counts[key]=len(cards)
    for card in cards:
        identity=re.search(r'>(HF-\d+) / ([^<]+)</span>',card)
        title=re.search(r'class="directory-card-link"[^>]*><h2[^>]*>(.*?)</h2>',card,re.S)
        link=re.search(r'href="(/live/discovery[^"?]+)" class="directory-card-link"',card)
        if not all((identity,title,link)):
            raise RuntimeError(f'Incomplete {key} card')
        ident=identity[1]
        if ident in rows: raise RuntimeError(f'Duplicate across departments {ident}')
        name=html.unescape(re.sub('<[^>]+>','',title[1])).strip()
        relevant=bool(re.search(r'wind|wake|weather|climate|turbulen|CFD|hurricane|typhoon|atmospher|storm|extreme|convection',name,re.I))
        rows[ident]=dict(id=ident,title=name,domain=labels[key],proposer='网页目录未列；不能认定',status='Research（目录标签；执行状态见任务页）',wind_related='候选：标题命中，待按任务内容核' if relevant else '',url='https://hf-mission.com'+html.unescape(link[1]),snapshot=str(meta_path))
assert len(counts)==len(labels),counts
assert len(rows)==54,(len(rows),counts)
records=sorted(rows.values(),key=lambda x:int(x['id'][3:]))
with (root/'挑战全表_54条.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=records[0].keys());w.writeheader();w.writerows(records)
with (root/'挑战全表_54条.md').open('w',encoding='utf-8') as f:
    f.write('# HFM 挑战全表：真实 Chrome 分领域快照\n\n')
    f.write('官网目录显示 54 条；按 12 个领域 URL 分别存证后程序化去重，得到 54 个唯一 ID。出题人/团队在目录未逐项列出，不擅填；状态字段仅记录目录原样标签 Research，不代表任务执行完成。候选相关性仅为标题筛选。原始快照见每行末尾。\n\n')
    keys=['id','title','domain','proposer','status','wind_related','url','snapshot']
    f.write('| '+' | '.join(keys)+' |\n|'+'|'.join(['---']*len(keys))+'|\n')
    for r in records:f.write('| '+' | '.join(r[k].replace('|','\\|') for k in keys)+' |\n')
print('counts=',counts,'total=',len(records),'wind=',[(r['id'],r['title']) for r in records if r['wind_related']])
