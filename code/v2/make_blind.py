#!/usr/bin/env python3
"""Validate two complete real answer files, then create a blind grading packet."""
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path('./32_AI_Teaching_Lab/Teaching_Data_Spec/omniedu_zs_items_L26_v2.jsonl')
HASH = 'a25b6f7be74133d53a2bbcbc971a0876661b66ce7e69937479c77aafc09cd0af'
MODELS = {'A': 'OpenDCAI/Omni-Edu-9B', 'B': 'Qwen/Qwen3.5-9B'}
MODES = ('solve', 'diagnose', 'socratic')

def load():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == HASH
    items = [json.loads(line) for line in SOURCE.read_text().splitlines()]
    assert len(items) == len({x['id'] for x in items}) == 20
    answer = {}
    for label, model in MODELS.items():
        rows = [json.loads(line) for line in (HERE / f'answers_{label}.jsonl').read_text().splitlines()]
        assert len(rows) == 60, (label, len(rows))
        expected = {(item['id'], mode) for item in items for mode in MODES}
        got = {(r['id'], r['task_mode']) for r in rows}
        assert len(got) == len(rows) and got == expected, (label, len(got), len(expected - got))
        for row in rows:
            assert set(row) == {'id', 'task_mode', 'model', 'answer', 'tokens', 'truncated'}
            assert row['model'] == model and isinstance(row['answer'], str)
            assert isinstance(row['tokens'], int) and row['tokens'] >= 0
            assert type(row['truncated']) is bool
            answer[(row['id'], row['task_mode'], label)] = row
    return items, answer

def main():
    for name in ('blind_pack.md', 'key.json'):
        assert not (HERE / name).exists(), f'Refuse overwrite: {name}'
    items, answer = load()
    rng = random.Random(261420)
    pairs = [(item, mode) for item in items for mode in MODES]
    rng.shuffle(pairs)
    key = {'input_sha256': HASH, 'seed': 261420, 'pairs': {}}
    lines = ['# L26.14 v2 盲评包', '', '60 个题目×任务项，顺序打散。X/Y 对应模型仅见单独的 key.json。评分依据以题集说明为准；此包不含参考答案。', '']
    for n, (item, mode) in enumerate(pairs, 1):
        labels = ['A', 'B']
        rng.shuffle(labels)
        pair_key = f"{item['id']}::{mode}"
        key['pairs'][pair_key] = {'X': MODELS[labels[0]], 'Y': MODELS[labels[1]]}
        lines += [f"## {n}. {item['id']} · {mode}", '', '题目：', item['question'], '']
        if mode == 'diagnose':
            lines += ['学生作答：', item['student_answer'], '']
        if mode == 'socratic':
            lines += ['学生消息：', item['socratic_student_msg'], '']
        for xy, label in zip(('X', 'Y'), labels):
            lines += [f'### {xy}', '', answer[(item['id'], mode, label)]['answer'], '']
    # Files are written only after the entire validation above passed.
    (HERE / 'blind_pack.md').write_text('\n'.join(lines), encoding='utf-8')
    (HERE / 'key.json').write_text(json.dumps(key, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('validated', len(items), 'items', len(answer), 'answers;', len(pairs), 'blind pairs')
    print('truncated', {label: sum(answer[(item['id'],mode,label)]['truncated'] for item in items for mode in MODES) for label in MODELS})

if __name__ == '__main__':
    main()
