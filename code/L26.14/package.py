"""Package completed L26.14 answer files for blind human scoring; no model inference."""
import hashlib
import json
import pathlib
import random
import secrets

BASE = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path('./32_AI_Teaching_Lab/Teaching_Data_Spec/omniedu_zs_items_v1.jsonl')
EXPECTED = '157e1d4ea05d1a8c06f7148a8107edfdfb9950b3ec29a7b49a32a2c284fabde3'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
items = [json.loads(line) for line in SOURCE.read_text().splitlines()]
assert len(items) == 30 and len({item['id'] for item in items}) == 30
answers = {}
for label in ('A', 'B'):
    path = BASE / f'answers_{label}.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 30 and len({row['id'] for row in rows}) == 30
    assert {row['id'] for row in rows} == {item['id'] for item in items}
    assert all(row['answer'] and type(row['tokens']) is int and type(row['truncated']) is bool for row in rows)
    assert len({row['model'] for row in rows}) == 1
    answers[label] = {row['id']: row for row in rows}
assert answers['A'][items[0]['id']]['model'] != answers['B'][items[0]['id']]['model']
seed = secrets.randbits(128)
rng = random.Random(seed)
rng.shuffle(items)
key = {'seed': seed, 'source_sha256': EXPECTED, 'mapping': {}}
parts = ['# L26.14 零样本盲评包', '', '题目顺序已混排；每题 X/Y 独立随机，映射只在单独的 key.json。这里不包含参考答案或评分细则。', '']
for idx, item in enumerate(items, 1):
    labels = ['A', 'B']
    rng.shuffle(labels)
    ident = item['id']
    key['mapping'][ident] = {blind: {'model_label': original, 'model': answers[original][ident]['model']} for blind, original in zip(('X', 'Y'), labels)}
    parts += [f'## {idx}. {ident}（{item["task_mode"]}）', '', item['question'], '']
    if item['task_mode'] == 'diagnose':
        parts += ['学生作答：' + item['student_answer'], '']
    for blind, original in zip(('X', 'Y'), labels):
        row = answers[original][ident]
        parts += [f'### {blind}', '', row['answer'], '', f'（生成 token：{row["tokens"]}；截断：{"是" if row["truncated"] else "否"}）', '']
(BASE / 'blind_pack.md').write_text('\n'.join(parts), encoding='utf-8')
(BASE / 'key.json').write_text(json.dumps(key, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('packaged', len(items), 'questions;', {label: len(rows) for label, rows in answers.items()})
