"""Score the frozen sanity split on both val and holdout after training."""
import json
from pathlib import Path
import numpy as np
import torch
import sys

ROOT = Path('/content/v6_work')
CODE = ROOT / 'v6_legacy_code'
sys.path.insert(0, str(ROOT))
import v6_run_segment as runner
from shared.configs.schema import TrainConfig
from shared import train as legacy
from shared.eval_module import EvalModule

out = ROOT / 'sanity'
summary = json.loads((out / 'segment_summary.json').read_text())
config = TrainConfig.model_validate(json.loads((out / 'train_config.json').read_text()))
assert summary['segment'] == 'sanity' and config.seed == 2
model_cls = legacy._resolve_model_cls(config)
model = model_cls(**legacy._model_kwargs_for_cfg(model_cls, config))
model.load_state_dict(torch.load(out / 'model_selected_val_r2.pt', map_location='cpu', weights_only=True))
model.cuda().eval()
evaluator = EvalModule(config.split_manifest_path, config.data_dir)
bundle = torch.load(CODE / 'all_data.pt', map_location='cpu', weights_only=False)
original_predict = evaluator._predict

def cached_split(split, seed=1):
    cases = set(evaluator.manifest['seeds'][str(seed)][split])
    names, p2c = bundle['case_names'], bundle['patch_to_case']
    indices = [i for i in range(len(p2c)) if names[int(p2c[i])] in cases]
    ids = torch.tensor(indices, dtype=torch.long)
    return dict(X=bundle['X'][ids], Y=bundle['Y'][ids], case_names=names,
                patch_to_case=p2c[ids], raw_cases=bundle['raw_cases'])

def with_features(model, X, batch_size, device):
    return original_predict(model, legacy._compute_sdf_features(X, config.input_features), batch_size, device)

evaluator._load_split = cached_split
evaluator._predict = with_features
val = evaluator.evaluate(model, split='val', seed=2, device=torch.device('cuda'))
holdout = evaluator.evaluate(model, split='holdout', seed=2, device=torch.device('cuda'))
combined = {**val['per_case_r2'], **holdout['per_case_r2']}
assert len(combined) == len(val['per_case_r2']) + len(holdout['per_case_r2'])
gate = {'selected_epoch': summary['epoch'], 'val_median_r2': val['r2_median'],
        'holdout_median_r2': holdout['r2_median'], 'total_median_r2': float(np.median(list(combined.values()))),
        'val_n': len(val['per_case_r2']), 'holdout_n': len(holdout['per_case_r2']),
        'per_case_r2': combined}
assert gate['val_n'] == 55 and gate['holdout_n'] == 47, gate
(out / 'sanity_gate.json').write_text(json.dumps(gate, indent=2))
print('SANITY_GATE', {k:v for k,v in gate.items() if k!='per_case_r2'}, flush=True)
