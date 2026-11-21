"""Run on Colab CPU: verify unchanged 3/4 h coefficients, then fit all delays."""
import importlib.util
import json
from pathlib import Path
import pandas as pd

ROOT = Path('/content/m6')

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

old = load('m6_score_pre_section8')
new = load('m6_score')
for delay in (4, 3):
    df = pd.read_parquet(ROOT / f'train_pairs_delay{delay}.parquet')
    previous = old.fit(df)
    amended = new.fit(df)
    assert previous['coefs'] == amended['coefs'], f'delay {delay}: coefficient changed'
    assert previous['tau'] == amended['tau'], f'delay {delay}: tau changed'
    assert previous['residuals'] == amended['residuals'], f'delay {delay}: residual changed'
    assert amended['skipped_buckets'] == [], f'delay {delay}: unexpected skip'
    print('UNCHANGED', delay, len(previous['coefs']), flush=True)

new.run_train()
models = json.loads((ROOT / 'models.json').read_text())
for delay in (4, 3):
    assert models[str(delay)]['skipped_buckets'] == []
skipped = models['6']['skipped_buckets']
assert len(skipped) == 12 * 4 and all(s['bucket'] == 0 for s in skipped), skipped
print('TRAIN_VERIFIED', len(skipped), 'structurally empty bucket entries', flush=True)
