"""Re-score the frozen v3 questions with the original per-item scorer."""
import json
from pathlib import Path
import score

root = Path(__file__).parent
score.items = {x['id']: x for x in map(json.loads, (root / 'eval_set_v3.jsonl').read_text().splitlines())}
rows = [json.loads(s) for s in (root / 'gemini_answers_v3.jsonl').read_text().splitlines()]
assert len(rows) == len(score.items) == len({x['id'] for x in rows}) == 100
assert all(x['status'] == 'ok' and x['model'] == 'gemini-3.8-flash-high' for x in rows)
summary = score.summary('Gemini 3.8 Flash high', rows)
for item in summary:
    group_rows = [x for x in rows if x['id'].startswith(item['group'])]
    item['thinking_tokens'] = sum(x['usage']['thinking_tokens'] for x in group_rows)
    item['total_tokens_reported'] = sum(x['usage']['total_tokens'] for x in group_rows)
    item['sum_item_duration_s'] = round(sum(x['duration_seconds'] for x in group_rows), 2)
    item['subscription_calls_per_1000'] = 1000
    item['subscription_usd'] = None
    item['incorrect_ids'] = [x['id'] for x in group_rows if not score.correct(score.items[x['id']], score.parsed(x['response']))]
(root / 'gemini_score_v3.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
