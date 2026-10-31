"""Run one preregistered 1000-epoch R11 segment on Colab; preserve 50-epoch states."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import torch

ROOT = Path('/content/v6_work')
CODE = ROOT / 'v6_legacy_code'
sys.path.insert(0, str(CODE / 'auto_v6'))
sys.path.insert(0, str(CODE / 'auto_v2/full_dataset/scripts'))
from shared.configs.schema import TrainConfig
from shared import train as legacy
from shared.eval_module import EvalModule


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segment', choices=['sanity', 'group'], required=True)
    args = ap.parse_args()
    assert digest(CODE / 'auto_v6/shared/train.py') == '9324e742ad0e48f3ef103cd7eb2d703568f3a6d560d629bf77a2aada84074c8a'
    assert digest(CODE / 'auto_v6/shared/eval_module.py') == 'cbf2c3781b64eaad74f2b1eb00bfb874bc815b1e5df8d19a71db758b06003560'
    assert digest(CODE / 'all_data.pt') == '494c85166bfc958449dcf753467675cf8d6da429c7edad4a74ec740210c6a5b9'
    config = dict(experiment_id='v6_'+args.segment, strategy='v6_preregistered',
        arch_name='anisotropic_kernel_operator_unet', arch_kwargs={'n_c':20,'depth':6},
        loss_name='masked_l1_gradient', loss_kwargs={}, seed=2 if args.segment=='sanity' else 17,
        epochs=1000, lr=0.0004, batch_size=16, checkpoint_interval=50,
        input_features='height_sdf_normal', eval_splits=['val'],
        data_dir=str(CODE), results_dir=str(ROOT / args.segment),
        split_manifest_path=str(ROOT / ('sanity_manifest.json' if args.segment=='sanity' else 'group_manifest.json')),
        heartbeat_interval_epochs=10, script_path=str(CODE/'auto_v6/campaigns/auto_v6/runs/r011_full_anisotropic_kernel_operator_unet_nc20_d6_height_sdf_normal_none_lr0.0004_masked_l1_gradient/model.py'),
        compute_r2=False, early_stop_wall_min=10000, max_wall_min=10000)
    cfg = TrainConfig.model_validate(config)
    outdir = Path(cfg.results_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir/'train_config.json').write_text(json.dumps(config,indent=2))
    original_save = torch.save
    def save_and_keep(obj, f, *a, **kw):
        result = original_save(obj, f, *a, **kw)
        if str(f) == str(outdir/'checkpoint.pt') and isinstance(obj,dict):
            ep = obj['epoch']
            shutil.copy2(f, outdir/f'checkpoint_ep{ep:04d}.pt')
        return result
    torch.save = save_and_keep
    started = time.time()
    try:
        metrics = legacy.train(cfg)
    finally:
        torch.save = original_save
    print('TRAIN_DONE', args.segment, metrics.get('status'), metrics.get('epochs_trained'), time.time()-started, flush=True)
    if metrics.get('status') != 'ok' or metrics.get('epochs_trained') != 1000:
        raise RuntimeError('Training incomplete: '+str(metrics.get('error_message')))

    # Restore the exact old raw-domain scoring, choosing only val checkpoints.
    evaluator = EvalModule(cfg.split_manifest_path, cfg.data_dir)
    bundle = torch.load(CODE/'all_data.pt',map_location='cpu',weights_only=False)
    original_load = evaluator._load_split
    def cached_split(split, seed=1):
        cases=set(evaluator.manifest['seeds'][str(seed)][split])
        names=bundle['case_names']
        p2c=bundle['patch_to_case']
        indices=[i for i in range(len(p2c)) if names[int(p2c[i])] in cases]
        ids=torch.tensor(indices,dtype=torch.long)
        return dict(X=bundle['X'][ids],Y=bundle['Y'][ids],case_names=names,
                    patch_to_case=p2c[ids],raw_cases=bundle['raw_cases'])
    evaluator._load_split = cached_split
    orig_predict=evaluator._predict
    def with_features(model,X,batch_size,device):
        return orig_predict(model,legacy._compute_sdf_features(X,cfg.input_features),batch_size,device)
    evaluator._predict=with_features
    cls=legacy._resolve_model_cls(cfg)
    model=cls(**legacy._model_kwargs_for_cfg(cls,cfg)).cuda()
    scores=[]
    for checkpoint in sorted(outdir.glob('checkpoint_ep*.pt')):
        state=torch.load(checkpoint,map_location='cpu',weights_only=False)
        epoch=int(state['epoch'])
        model.load_state_dict(state['model_state_dict'])
        val=evaluator.evaluate(model,split='val',seed=cfg.seed,device=torch.device('cuda'))
        scores.append({'epoch':epoch,'val_r2_median':val['r2_median'],'val_n':val['n_cases_evaluated'],'val_failed':val['n_fail']})
        (outdir/'checkpoint_selection.json').write_text(json.dumps(scores,indent=2))
        print('VAL',args.segment,epoch,val['r2_median'],val['n_cases_evaluated'],flush=True)
    winner=max(scores,key=lambda row:(row['val_r2_median'],-row['epoch']))
    ckpt=outdir/f"checkpoint_ep{winner['epoch']:04d}.pt"
    model.load_state_dict(torch.load(ckpt,map_location='cpu',weights_only=False)['model_state_dict'])
    selected=outdir/'model_selected_val_r2.pt'
    original_save(model.state_dict(),selected)
    holdout=evaluator.evaluate(model,split='holdout',seed=cfg.seed,device=torch.device('cuda'))
    summary={'segment':args.segment,'checkpoint':str(selected),'epoch':winner['epoch'],
             'val_median_r2':winner['val_r2_median'],'holdout_median_r2':holdout['r2_median'],
             'holdout_n':holdout['n_cases_evaluated'],'holdout_failed':holdout['n_fail'],
             'holdout_per_case_r2':holdout['per_case_r2'],
             'train_wall_seconds':metrics['wall_time_sec'],'selection_wall_seconds':time.time()-started-metrics['wall_time_sec'],
             'gpu':metrics['gpu'],'peak_vram_gb':metrics['peak_vram_gb']}
    (outdir/'segment_summary.json').write_text(json.dumps(summary,indent=2))
    print('SEGMENT_DONE',json.dumps({k:v for k,v in summary.items() if k!='holdout_per_case_r2'}),flush=True)

if __name__=='__main__':
    main()
