"""Build one immutable book blind set from read-only index and original PDF pages.
No rc-kb queries and no platform handoff. Fails closed before freezing on bad evidence.
"""
import collections
import hashlib
import json
import pathlib
import re
import sqlite3
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
DB = './ftkb/index.sqlite'
MANIFEST = pathlib.Path('./ftkb_ocr/page_manifest_dedup.jsonl')
# group, source key, PDF physical page, Chinese paraphrase, reference answer, literal page anchor
ITEMS = [
    ('book', '2NFEY432', 85, '正弦土壤导热近似中，地表温度峰值比地面热通量峰值滞后多少？换算到日周期和年周期各是多久？', '周期的 1/8；日周期约 3 小时，年周期约 1.5 个月。', 'P/8, or 3 h'),
    ('book', 'BIISKYQH', 100, '蛙跳格式配上不稳定边界条件时，为什么振荡可能出现在离失稳边界很远的另一端？', '寄生模态会以与原微分方程相反的方向传播误差；失稳增长缓慢使振荡可到达另一端。', 'parasitic mode for the leapfrog scheme'),
    ('book', 'BFU4V2FN', 90, '两组热带气旋生成试验对初值微小扰动的敏感性结论相反，由此提出哪种预报体系值得尝试？', '热带气旋生成的集合预报体系。', 'prediction system for TC formation'),
    ('book', '8AUYKNGT', 110, '与流动失稳或结构运动无关的外源激励，列出的五类常见来源是什么？', '湍流、空化及部分两相流、振荡流（含波浪）、机器及机械部件、地震。', 'Among the most common sources of EIE are:'),
    ('book', 'W3MNXCR9', 93, '热带气旋暖核形成时，除水平平流与扩散之外，哪两条热力途径被指出可能产生暖中心？', '下沉增温，或潜热加热超过绝热冷却。', 'warm core must be produced'),
    ('book', '6YX25D66', 50, '高频测力天平用于高楼动力风荷载时，适用对象主要响应在哪三种基础振型？', '两个方向的侧摆和扭转三个基本模态。', 'three fundamental modes of vibration'),
    ('book', 'Y8V97HH7', 110, 'Angstrom 散射幂指数在一般条件下约为多少？遇到沙尘或火山灰等大粒子时可能降至什么范围？', '一般约 1.3；大粒子污染时可降至 0.5 或更低。', 'may fall off to 0.5 or less'),
    ('book', 'YYK5BIZH', 132, '比较飓风和冬季温带气旋的垂直热结构：前者的暖核与后者的冷核分别集中在哪里？', '飓风在对流层中层有集中暖核；温带气旋在对流层中、上层有冷核。', 'a core of very cold air in the middle and upper troposphere'),
    ('book_ocr', 'Y7BVKBMV', 110, '激波捕捉计算为何通常偏好守恒形式，而不是直接以原始变量写成非守恒形式？', '守恒形式以通量变量为依变量，跨激波这些通量的变化为零或较小，数值捕捉质量因此较好。', 'flux variables as the dependent variables'),
    ('book_ocr', 'KGWUXMNQ', 55, '无穷级数绝对收敛与通常收敛之间，哪个方向的蕴含必然成立，逆命题呢？', '绝对收敛必然推出收敛；收敛不一定推出绝对收敛。', 'Absolute convergence implies convergence'),
    ('book_ocr', '7LUSTFFE', 82, '尾流、混合层与几类射流在足够下游呈现自相似时，近源几何和流动条件的重要性如何变化？', '近源的几何与流动条件细节逐渐变得不重要，缩放后速度廓线形状相同。', 'details of the geometry and flow conditions'),
    ('book_ocr', '7BJLSXUD', 100, '在连续函数的加权欧氏范数定义里，权函数在开区间内部须满足什么条件？端点允许何种例外？', '权函数在开区间连续且严格为正；端点允许可积奇异性。', 'Integrable singulari-'),
]

def norm(x):
    return re.sub(r'\s+', ' ', x).casefold()

def run(args, data=None, timeout=120):
    p = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{args[0]} exit={p.returncode}: {p.stderr[:300]!r}')
    return p.stdout

assert len(ITEMS) == 12
assert not any((ROOT / x).exists() for x in ('questions_blind.jsonl', 'freeze.sha256', 'source_page_check.jsonl', 'README.md')), 'frozen targets exist; never overwrite'
conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
ocr_lookup = {}
for line in MANIFEST.open(encoding='utf-8'):
    m = json.loads(line)
    if (m['canonical_key'], m['physical_page']) in {(key, page) for _, key, page, *_ in ITEMS if key in {'Y7BVKBMV','KGWUXMNQ','7LUSTFFE','7BJLSXUD'}}:
        ocr_lookup[(m['canonical_key'], m['physical_page'])] = m
rows, checks = [], []
prior = {r['source_key'] for r in map(json.loads, (ROOT.parent / 'blind_round3' / 'questions_blind.jsonl').open(encoding='utf-8'))}
for i, (group, key, page, question, answer, anchor) in enumerate(ITEMS, 1):
    assert page > 10 and group in {'book', 'book_ocr'}
    assert not re.search(r'书|教材|专著|手册|报告|学位论文|book|textbook|thesis|report|handbook', question, re.I), question
    if group == 'book':
        record = conn.execute('SELECT attachment,title,text,pdf,type FROM pages WHERE key=? AND page=? LIMIT 1', (key,page)).fetchone()
        assert record and record[4] in {'book','bookSection'}, (key,page)
        attachment,title,text,pdf,_ = record
        assert norm(anchor) in norm(text), ('index anchor missing', key,page)
        result = run(['pdftotext', '-f', str(page), '-l', str(page), '-layout', pdf, '-']).decode('utf-8',errors='replace')
        method = 'pdftotext -f P -l P -layout original PDF physical page'
        assert norm(anchor) in norm(result), ('PDF anchor missing',key,page)
        assert len(result.strip()) > 200, ('not text layer',key,page)
    else:
        m = ocr_lookup[key,page]
        pdf = m['source_pdf']; attachment = key; title = pathlib.Path(pdf).stem
        assert norm(anchor) in norm(pathlib.Path(m['text_path']).read_text(encoding='utf-8')), ('manifest OCR anchor missing',key,page)
        assert not run(['pdftotext','-f',str(page),'-l',str(page),pdf,'-']).strip(), ('OCR page has original text layer',key,page)
        image = run(['pdftoppm','-f',str(page),'-l',str(page),'-r','180','-singlefile','-png',pdf])
        result = run(['tesseract','stdin','stdout','-l','eng'],image).decode('utf-8',errors='replace')
        method = 'pdftoppm physical page 180 dpi -> independent tesseract eng re-OCR'
        assert norm(anchor) in norm(result), ('re-OCR anchor missing',key,page)
    id_ = f'R4-{i:02d}'
    rows.append(dict(id=id_,group=group,question=question,answer=answer,source_key=key,attachment=attachment,title=title,pdf_page=page,source_pdf=pdf,evidence_anchor=anchor,ocr=(group=='book_ocr')))
    checks.append(dict(id=id_,method=method,anchor_found=True,physical_page=page,source_key=key,source_pdf=pdf,exit_code=0,render_or_text_chars=len(result),original_text_layer=(group=='book')))
assert len(set(x['source_key'] for x in rows)) == 12
assert sum(x['group']=='book_ocr' for x in rows) >= 4
assert len(set(x['source_key'] for x in rows) - prior) >= 8
ROOT.mkdir(parents=True, exist_ok=True)
question_bytes = ''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows).encode('utf-8')
check_bytes = ''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in checks).encode('utf-8')
# Exclusive creation: do not modify any existing results. All source checks complete before freeze.
with (ROOT/'source_page_check.jsonl').open('xb') as f: f.write(check_bytes)
with (ROOT/'questions_blind.jsonl').open('xb') as f: f.write(question_bytes)
sha = hashlib.sha256(question_bytes).hexdigest()
with (ROOT/'freeze.sha256').open('x') as f: f.write(f'{sha}  questions_blind.jsonl\n')
print('FROZEN',len(rows),dict(collections.Counter(x['group'] for x in rows)),'new sources',len(set(x['source_key'] for x in rows)-prior),'sha256',sha)
