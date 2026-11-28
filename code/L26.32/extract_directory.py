"""Extract only visible challenge cards from archived real-Chrome HTML."""
import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / 'snapshots/20261126_232149_01_hf-mission.com.html'
body = SOURCE.read_text(encoding='utf-8')
cards = re.findall(r'<article data-v-138bb890="">(.*?)</article>', body, re.S)
rows = []
for card in cards:
    identity = re.search(r'>(HF-\d+) / ([^<]+)</span>', card)
    title = re.search(r'class="directory-card-link"[^>]*><h2[^>]*>(.*?)</h2>', card, re.S)
    link = re.search(r'href="(/live/discovery[^"?]+)" class="directory-card-link"', card)
    if not (identity and title and link):
        raise RuntimeError(f'incomplete card {len(rows)+1}')
    name = html.unescape(re.sub('<[^>]+>', '', title[1])).strip()
    # These are title-keyword candidates, not verified scientific relevance.
    relevant = bool(re.search(r'wind|wake|weather|climate|turbulen|CFD|hurricane|typhoon|atmospher|storm|extreme', name, re.I))
    rows.append(dict(id=identity[1], title=name, domain='目录未逐项标示', proposer='目录未列', status=identity[2], wind_candidate='标题命中，待任务页核' if relevant else '', url='https://hf-mission.com'+html.unescape(link[1])))
ids = [r['id'] for r in rows]
if len(ids) != len(set(ids)):
    raise RuntimeError('duplicate ID')
with (ROOT/'挑战目录_可见50条.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
with (ROOT/'挑战目录_可见50条.md').open('w',encoding='utf-8') as f:
    f.write('# HFM 真浏览器目录快照的可见条目（非全表）\n\n')
    f.write(f'来源：{SOURCE.name}；目录显示总数 54，快照 DOM 仅 {len(rows)} 个条目，尚缺 4；未翻页。出题方与领域不是目录逐项字段，不猜填。\n\n')
    f.write('| 编号 | 标题 | 领域 | 出题方 | 状态 | 风相关候选 | 链接 |\n|---|---|---|---|---|---|---|\n')
    for r in rows:
        f.write('| ' + ' | '.join(r[k].replace('|','\\|') for k in ['id','title','domain','proposer','status','wind_candidate','url']) + ' |\n')
print('visible',len(rows),'unique',len(set(ids)),'wind candidates',[(r['id'],r['title']) for r in rows if r['wind_candidate']])
