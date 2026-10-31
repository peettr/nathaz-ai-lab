from pathlib import Path
p=Path('/content/a3_b2_1014')
print('GATELOG', (p/'gate.log').read_text(errors='replace')[-3500:] if (p/'gate.log').exists() else 'missing',flush=True)
print('METRICS', (p/'gate_metrics.jsonl').read_text()[-2000:] if (p/'gate_metrics.jsonl').exists() else 'missing',flush=True)
