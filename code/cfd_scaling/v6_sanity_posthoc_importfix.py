"""Posthoc checkpoint selection after the 1000-epoch training-only success.
The immutable legacy evaluator is unchanged; add its v2 references import path.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch
ROOT=Path('/content/v6_work')
CODE=ROOT/'v6_legacy_code'
sys.path.insert(0,str(CODE/'auto_v6'))
sys.path.insert(0,str(CODE/'auto_v2/full_dataset/references'))
sys.path.insert(0,str(CODE/'auto_v2/full_dataset/scripts'))
from shared.configs.schema import TrainConfig
from shared import train as legacy
from shared.eval_module import EvalModule
out=ROOT/'sanity'
config=TrainConfig.model_validate(json.loads((out/'train_config.json').read_text()))
assert config.seed==2 and config.epochs==1000
metrics=json.loads((out/'metrics.json').read_text())
assert metrics['epochs_trained']==1000
bundle=torch.load(CODE/'all_data.pt',map_location='cpu',weights_only=False)
ev=EvalModule(config.split_manifest_path,config.data_dir)
def cached_split(split,seed=1):
    cases=set(ev.manifest['seeds'][str(seed)][split]); names=bundle['case_names']; p2c=bundle['patch_to_case']
    ids=torch.tensor([i for i in range(len(p2c)) if names[int(p2c[i])] in cases],dtype=torch.long)
    return dict(X=bundle['X'][ids],Y=bundle['Y'][ids],case_names=names,patch_to_case=p2c[ids],raw_cases=bundle['raw_cases'])
ev._load_split=cached_split
orig_predict=ev._predict
def with_features(model,X,batch_size,device):
    return orig_predict(model,legacy._compute_sdf_features(X,config.input_features),batch_size,device)
ev._predict=with_features
cls=legacy._resolve_model_cls(config)
model=cls(**legacy._model_kwargs_for_cfg(cls,config)).cuda()
scores=[]; start=time.time()
for ckpt in sorted(out.glob('checkpoint_ep*.pt')):
    state=torch.load(ckpt,map_location='cpu',weights_only=False)
    model.load_state_dict(state['model_state_dict'])
    val=ev.evaluate(model,split='val',seed=config.seed,device=torch.device('cuda'))
    row={'epoch':int(state['epoch']),'val_r2_median':val['r2_median'],'val_n':val['n_cases_evaluated'],'val_failed':val['n_fail']}
    scores.append(row)
    (out/'checkpoint_selection.json').write_text(json.dumps(scores,indent=2))
    print('VAL',row,flush=True)
assert len(scores)==20 and all(x['val_n']==55 and x['val_failed']==0 for x in scores),scores
winner=max(scores,key=lambda x:(x['val_r2_median'],-x['epoch']))
state=torch.load(out/f"checkpoint_ep{winner['epoch']:04d}.pt",map_location='cpu',weights_only=False)
model.load_state_dict(state['model_state_dict'])
val=ev.evaluate(model,split='val',seed=2,device=torch.device('cuda'))
holdout=ev.evaluate(model,split='holdout',seed=2,device=torch.device('cuda'))
combined={**val['per_case_r2'],**holdout['per_case_r2']}
assert len(val['per_case_r2'])==55 and len(holdout['per_case_r2'])==47 and len(combined)==102
summary={'segment':'sanity','epoch':winner['epoch'],'checkpoint':str(out/'model_selected_val_r2.pt'),
    'val_median_r2':val['r2_median'],'holdout_median_r2':holdout['r2_median'],
    'total_median_r2':float(np.median(list(combined.values()))),
    'val_n':55,'holdout_n':47,'train_wall_seconds':metrics['wall_time_sec'],
    'selection_wall_seconds':time.time()-start,'gpu':metrics['gpu'],'peak_vram_gb':metrics['peak_vram_gb'],
    'per_case_r2':combined,'posthoc_import_fix':'Added auto_v2/full_dataset/references to sys.path; immutable eval_module unchanged'}
(out/'segment_summary.json').write_text(json.dumps(summary,indent=2))
torch.save(model.state_dict(),out/'model_selected_val_r2.pt')
print('SANITY_GATE',{k:v for k,v in summary.items() if k not in ('per_case_r2','checkpoint')},flush=True)
