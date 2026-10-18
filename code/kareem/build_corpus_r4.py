#!/usr/bin/env python3
"""只读并入第五批；仅创建 _r4 成果，遇到已有成果立即停止。"""
import ast
import collections
import csv
import pathlib
import re
import unicodedata

P = pathlib.Path(__file__).resolve().parent
BATCH = pathlib.Path('./.hermes/profiles/researchos-literature/artifacts/kareem_round5/kareem_r5_215_total_results_v11.csv')
STATES = ('库内有全文', '库内只有题录', '不在库')

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def norm(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower())

def doi(s):
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', (s or '').strip().lower())

def save(path, rows, fields):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='raise')
        w.writeheader()
        w.writerows(rows)

def route(row, reason):
    text = reason.lower()
    # No verified bibliographic identity is not an access denial.
    identity = ('题录身份', '未核作者', '题名与 kareem 作者', '题名候选', '精确作品',
                '题名检索', 'closest result not same', '身份/边界', '目标贡献身份',
                'title_mismatch', '候选 pdf 标题', '候选同题 pdf', '版本/doi')
    if any(s in text for s in identity):
        return '无正式页面待核'
    # A formally located publisher PDF may require an institutional session.
    publisher = ('出版社', '授权浏览器', 'publisher', '403', 'just a moment',
                 '登录', 'pdf 控件', 'pdf control', 'access controls', 'springer')
    if any(s in text for s in publisher):
        return '学校账号浏览器'
    # Older proceedings/books/no working PDF: ILL is a route to test, not proof of access denial.
    if row['type'] in ('proceedings', 'book-chapter', '其他:book') or any(s in text for s in
       ('馆际', '预览', '404', '无可用链接', '没有oa', '未给 oa', '无法找到', 'not_pdf', '合刊', 'no verified', 'not_acquired')):
        return '馆际互借'
    if not row['doi'] and not row['oa_url']:
        return '无正式页面待核'
    return '学校账号浏览器' if row['doi'] else '馆际互借'

def esc(s):
    return str(s or '').replace('|', '/').replace('\n', ' ')

rows = read(P / 'corpus_status_r3.csv')
batch = read(BATCH)
assert len(rows) == len({x['openalex_id'] for x in rows}) == 511
assert len(batch) == 215
assert collections.Counter(x['result'] for x in batch) == {'imported': 73, 'blocked': 3, 'other': 120, 'non_paper': 19}
by_doi = collections.defaultdict(list)
by_title = collections.defaultdict(list)
for x in rows:
    if doi(x['doi']):
        by_doi[doi(x['doi'])].append(x)
    if norm(x['title']):
        by_title[norm(x['title'])].append(x)
seen = set()
for x in batch:
    matches = by_doi[doi(x['doi'])] if doi(x['doi']) else by_title[norm(x['title'])]
    assert len(matches) == 1, (x['title'], x['doi'], len(matches))
    r = matches[0]
    assert r['openalex_id'] not in seen, r['openalex_id']
    seen.add(r['openalex_id'])
    assert norm(r['title']) == norm(x['title']) or norm(r['title'])[:45] == norm(x['title'])[:45], (r['title'], x['title'])
    assert r['status'] == '不在库' and not r['duplicate_of'] and not r['round4_result'], (r['title'], r['status'])
    assert r['openalex_id'] in {z['openalex_id'] for z in read(P / 'to_fetch_r5.csv')}, r['openalex_id']
    r['round5_result'] = x['result']
    r['round5_reason'] = x['reason']
    r['intake_batch'] = (r['intake_batch'] + ';' if r['intake_batch'] else '') + 'fifth'
    if x['result'] == 'imported':
        assert all(x[k] for k in ('zotero_parent_key', 'pdf_child_key', 'local_pdf_path'))
        assert pathlib.Path(x['local_pdf_path']).is_file(), x['local_pdf_path']
        r['status'] = '库内有全文'
        r['access_result'] = 'attached_verified'
        r['zotero_parent_key'] = x['zotero_parent_key']
        r['pdf_child_key'] = x['pdf_child_key']
        r['pdf_path'] = x['local_pdf_path']
        add = '第五批来源回执：目标 PDF 与云端附件已核；本次仅核路径存在，不等于 Windows 本地同步'
    elif x['result'] == 'non_paper':
        r['status'] = 'non_paper'
        r['access_result'] = 'round5_non_paper'
        add = '第五批：非独立研究论文，剔出论文分母'
    else:
        r['access_result'] = 'round5_' + x['result']
        add = '第五批仍未获经验证目标全文'
    r['note'] = (r['note'] + '；' if r['note'] else '') + add
assert len(seen) == 215
assert all(x['status'] == '库内有全文' for x in rows if x.get('round5_result') == 'imported')
active = [x for x in rows if not x['duplicate_of'] and x['status'] not in ('not_kareem', 'non_paper')]
counts = collections.Counter(x['status'] for x in active)
assert len(active) == 476 and counts == {'库内有全文': 322, '库内只有题录': 9, '不在库': 145}, (len(active), counts)
assert sum(bool(x['duplicate_of']) for x in rows) == 1
assert sum(x['status'] == 'not_kareem' for x in rows) == 1
assert sum(x['status'] == 'non_paper' for x in rows) == 33

missing = []
for x in active:
    if x['status'] == '库内有全文':
        continue
    reason = x.get('round5_reason') or x.get('round4_reason') or x['note'] or '仅有题录；未见针对目标全文的已记录失败原因，尚未核实可得性'
    missing.append(dict(openalex_id=x['openalex_id'], title=x['title'], year=x['year'], venue=x['venue'],
                        doi=x['doi'], cited_by=x['cited_by'], status=x['status'],
                        last_failure_reason=reason, suggested_route=route(x, reason), last_attempt_batch=x['intake_batch'],
                        oa_url=x['oa_url']))
missing.sort(key=lambda x: (-int(x['cited_by'] or 0), x['openalex_id']))
assert len(missing) == 154 and len({x['openalex_id'] for x in missing}) == 154
assert {x['openalex_id'] for x in missing} == {x['openalex_id'] for x in active if x['status'] != '库内有全文'}
assert all(x['suggested_route'] in ('学校账号浏览器', '馆际互借', '无正式页面待核', '只能向作者要') for x in missing)

script = ast.parse((P / 'build_corpus_status.py').read_text())
topics = next(ast.literal_eval(node.value) for node in script.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'topics' for t in node.targets))
inv = {x['work_id']: x for x in read(P / 'inventory.csv')}
by_decade = collections.defaultdict(collections.Counter)
by_topic = collections.defaultdict(collections.Counter)
for x in active:
    decade = str(int(x['year']) // 10 * 10) + 's' if x['year'].isdigit() else '年不详'
    by_decade[decade][x['status']] += 1
    labels = ([z for z in inv[x['work_id']]['topic'].split(';') if z in topics or z == '风工程综合/其他待细分']
              if x['work_id'] in inv else [t for t, rx in topics.items() if re.search(rx, x['title'], re.I)])
    for label in labels or ['风工程综合/其他待细分']:
        by_topic[label][x['status']] += 1

# Preflight before named outputs: no publishing partial results on failed invariants.
outputs = [P / n for n in ('corpus_status_r4_checked.csv', 'still_missing_r4.csv', 'corpus_summary_r4.md')]
assert not any(path.exists() for path in outputs), 'r4 目标文件已存在；不得覆盖'
save(outputs[0], rows, list(rows[0]) + ['round5_result', 'round5_reason'])
save(outputs[1], missing, list(missing[0]))
route_counts = collections.Counter(x['suggested_route'] for x in missing)
with outputs[2].open('x', encoding='utf-8') as f:
    f.write('# Kareem 目录对库第四轮（第五批并入）\n\n')
    f.write('来源：本地冻结 OpenAlex 作者目录 A5069470138 的 r3 对账表、Literature 第五批 `kareem_r5_215_total_results_v11.csv` 与 `kareem_r5_continuation_phase_report_v11.md`；运行 `build_corpus_r4.py` 只读并表，不下载或重查数据库。第五批 215 条均由 DOI 或无 DOI 时完整题名唯一匹配到 `to_fetch_r5.csv` 的目录 ID：73 imported / 19 non_paper / 3 blocked / 120 other。导入 PDF 路径存在；云端父子项及 MD5 核对沿用 Literature 回执，本次未复验，不推定 Windows 端已同步。\n\n')
    f.write(f'目录原始 {len(rows)} ID；目录别名重复 1、非 Kareem 1、非独立研究论文 33（r3 14 + 本批 19），暂定论文分母 {len(active)}。有全文 {counts[STATES[0]]}（{counts[STATES[0]]/len(active):.1%}）；只有题录 {counts[STATES[1]]}（{counts[STATES[1]]/len(active):.1%}）；不在库 {counts[STATES[2]]}（{counts[STATES[2]]/len(active):.1%}）；题录覆盖 {(counts[STATES[0]]+counts[STATES[1]])/len(active):.1%}。这不是经逐篇作者身份和版本核实的全部 Kareem 独立作品数。\n\n')
    f.write('## 分轮口径比较\n\n| 轮次 | 分母 | 全文 | 只有题录 | 不在库 | 全文覆盖 | 题录覆盖 |\n|---|---:|---:|---:|---:|---:|---:|\n')
    for name, den, full, bib, absent in [('第一轮', 511, 116, 9, 386), ('第二轮', 494, 152, 9, 333), ('第三轮', 495, 249, 9, 237), ('第四轮', len(active), counts[STATES[0]], counts[STATES[1]], counts[STATES[2]])]:
        assert full + bib + absent == den
        f.write(f'| {name} | {den} | {full} | {bib} | {absent} | {full/den:.1%} | {(full+bib)/den:.1%} |\n')
    f.write('\n各轮分母不一致：第二轮曾暂排缩写作者，第三轮恢复并另剔非论文，第四轮再排 19 条；覆盖率变化不可全归因于 PDF 新增。`non_paper` 为“非独立研究论文”的统计口径，不等于没有学术价值；第五批其中有 Closure/Discussion、书评、前言、纪念文与技术报告。\n\n')
    f.write('## 按年代缺口\n\n| 年代 | 有全文 | 只有题录 | 不在库 | 合计 |\n|---|---:|---:|---:|---:|\n')
    for k in sorted(by_decade):
        c = by_decade[k]
        f.write(f'| {k} | {c[STATES[0]]} | {c[STATES[1]]} | {c[STATES[2]]} | {sum(c.values())} |\n')
    f.write('\n## 按主题缺口（题名粗分，多标签不可相加）\n\n有 work_id 的沿用 inventory 标签，其余用 `build_corpus_status.py` 的题名正则；“其他待细分”不作实质主题。\n\n| 主题 | 有全文 | 只有题录 | 不在库 | 合计 |\n|---|---:|---:|---:|---:|\n')
    for k in [*topics, '风工程综合/其他待细分']:
        c = by_topic[k]
        f.write(f'| {k} | {c[STATES[0]]} | {c[STATES[1]]} | {c[STATES[2]]} | {sum(c.values())} |\n')
    f.write(f'\n## 仍无全文及建议途径\n\n`still_missing_r4.csv` {len(missing)} 行 = 不在库 {counts[STATES[2]]} + 只有题录 {counts[STATES[1]]}；按 OpenAlex 快照被引数降序。分类建议（互斥、尚未执行）：\n\n| 建议途径 | 条数 |\n|---|---:|\n')
    for k in ('学校账号浏览器', '馆际互借', '无正式页面待核', '只能向作者要'):
        f.write(f'| {k} | {route_counts[k]} |\n')
    f.write('\n“上次失败原因”来自第五批优先、否则第四批或历史 note；仅有题录但没有明确失败回执的标“尚未核实”，不冒称访问被拦。分类只是下一步路径，不证明机构/馆际路线已穷尽；“只能向作者要”需要前两路失败的证据，本轮没有，故不标。此前 `corpus_status_extra_r2.csv` 的目录外本地作品没有进入 OpenAlex 分母，也不能被当作缺口。\n\n')
    f.write('## 缺口性质与投入建议\n\n')
    by_type = collections.Counter(x['type'] for x in active if x['status'] != '库内有全文')
    f.write('仍无全文的目录内候选按类型：' + '、'.join(f'{k} {v}' for k,v in by_type.most_common()) + '。')
    decades = collections.Counter((str(int(x['year'])//10*10)+'s' if x['year'].isdigit() else '年不详') for x in active if x['status'] != '库内有全文')
    f.write('按年代：' + '、'.join(f'{k} {v}' for k,v in sorted(decades.items())) + '。')
    f.write(f'被引前 20 条中仍无全文 {sum(x["status"] != "库内有全文" for x in sorted(active,key=lambda x:-int(x["cited_by"] or 0))[:20])} 条（OpenAlex 冻结快照）。')
    f.write('剩余包含会议/书章及早年目录记录，但也有期刊、近年作品，不能概括为全是低优先级；值得先核高被引且身份清楚的论文并试学校账号浏览器，其次依用途办理馆际互借。无正式页面/作者身份/版本未明的先核题录，不批量向作者索稿；投入前核第三 EndNote 库及同题异 DOI 版本。\n')
print('raw',len(rows),'active',len(active),'status',dict(counts),'r5',collections.Counter(x['result'] for x in batch),'still_missing',len(missing),'routes',dict(route_counts))
