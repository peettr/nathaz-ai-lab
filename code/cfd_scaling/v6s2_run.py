"""One immutable v6 stage-two run; 1000 epochs, 50-epoch val-R2 selection.
Requires hashed legacy code/data on Colab /content/v6_work/v6_legacy_code.
Do not launch until CRC data transfer and manifest/raw-evaluator parity pass.
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path('/content/v6_work')
CODE = ROOT / 'v6_legacy_code'
sys.path[:0] = [str(CODE/'auto_v6'), str(CODE/'auto_v2/full_dataset/scripts'),
                str(CODE/'auto_v2/full_dataset/references')]
from shared.configs.schema import TrainConfig
from shared import train as legacy
from shared.eval_module import EvalModule
from shared.eval_module import _per_case_r2

DATA_HASH = '494c85166bfc958449dcf753467675cf8d6da429c7edad4a74ec740210c6a5b9'


def sha(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for x in iter(lambda: f.read(2**20),b''):
            h.update(x)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, choices=(17,42,73), required=True)
    p.add_argument('--size', choices=('50','100','200','all'), required=True)
    p.add_argument('--manifest', type=Path, default=ROOT/'v6_nested_subsets.json')
    p.add_argument('--score-only', action='store_true', help='recover scoring after complete training, without retraining')
    p.add_argument('--run-tag', choices=('retry1',), default='',
                   help='new run root after the retained all/73 OOM probe; do not overwrite it')
    a = p.parse_args()
    assert not a.run_tag or (a.size, a.seed) == ('all', 73)
    assert sha(CODE/'all_data.pt') == DATA_HASH
    assert sha(CODE/'auto_v6/shared/train.py') == '9324e742ad0e48f3ef103cd7eb2d703568f3a6d560d629bf77a2aada84074c8a'
    assert sha(CODE/'auto_v6/shared/eval_module.py') == 'cbf2c3781b64eaad74f2b1eb00bfb874bc815b1e5df8d19a71db758b06003560'
    manifest = json.loads(a.manifest.read_text())
    row = manifest['seeds'][str(a.seed)][a.size]
    train, val, test = row['cases'], manifest['val_cases'], manifest['test_cases']
    assert len(train) == row['actual_cases'] and len(val) == 34 and len(test) == 100
    assert not (set(train)&(set(val)|set(test))) and not set(val)&set(test)
    key = f'v6s2_{a.size}_seed{a.seed}' + (f'_{a.run_tag}' if a.run_tag else '')
    out = ROOT/key
    if a.score_only:
        assert out.is_dir() and not (out/'summary.json').exists()
        cfg = TrainConfig.model_validate(json.loads((out/'train_config.json').read_text()))
        assert cfg.seed == a.seed and cfg.epochs == 1000
        score(out,cfg,a.seed)
        return
    assert not out.exists(), 'run root already exists: '+str(out)
    out.mkdir()
    # Old evaluator expects train/val/holdout partition keys.
    split_path = out/'split_manifest.json'
    split_path.write_text(json.dumps({'fmt_shape':640,'seeds':{str(a.seed):
                       {'train':train,'val':val,'holdout':test}}}))
    cfg_dict = dict(experiment_id=key,strategy='v6_preregistered',
        arch_name='anisotropic_kernel_operator_unet',arch_kwargs={'n_c':20,'depth':6},
        loss_name='masked_l1_gradient',loss_kwargs={},seed=a.seed,
        epochs=1000,lr=0.0004,batch_size=16,checkpoint_interval=50,
        input_features='height_sdf_normal',eval_splits=['val'],
        data_dir=str(CODE),results_dir=str(out),split_manifest_path=str(split_path),
        heartbeat_interval_epochs=10,script_path=str(CODE/'auto_v6/campaigns/auto_v6/runs/r011_full_anisotropic_kernel_operator_unet_nc20_d6_height_sdf_normal_none_lr0.0004_masked_l1_gradient/model.py'),
        compute_r2=False,early_stop_wall_min=10000,max_wall_min=10000)
    cfg = TrainConfig.model_validate(cfg_dict)
    (out/'train_config.json').write_text(json.dumps(cfg_dict,indent=2))
    original_save = torch.save
    def preserve(obj, path, *args, **kwargs):
        ret = original_save(obj,path,*args,**kwargs)
        if str(path) == str(out/'checkpoint.pt') and isinstance(obj,dict):
            shutil.copy2(path,out/f"checkpoint_ep{int(obj['epoch']):04d}.pt")
        return ret
    torch.save = preserve
    start = time.monotonic()
    try:
        metrics = legacy.train(cfg)
    finally:
        torch.save = original_save
    assert metrics.get('epochs_trained') == 1000, metrics
    # A post-training evaluator failure does NOT justify retraining; use --score-only.
    score(out,cfg, a.seed, start, metrics)


def score(out, cfg, seed, start=None, metrics=None):
    evaluator = EvalModule(cfg.split_manifest_path,cfg.data_dir)
    bundle = torch.load(CODE/'all_data.pt',map_location='cpu',weights_only=False)
    names,p2c = bundle['case_names'],bundle['patch_to_case']
    def cached(split, seed=1):
        requested = set(evaluator.manifest['seeds'][str(seed)][split])
        ids = torch.tensor([i for i in range(len(p2c)) if names[int(p2c[i])] in requested],dtype=torch.long)
        found = {names[int(p2c[i])] for i in ids.tolist()}
        assert found == requested, (split,requested-found)
        return dict(X=bundle['X'][ids],Y=bundle['Y'][ids],case_names=names,
                    patch_to_case=p2c[ids],raw_cases=bundle['raw_cases'])
    evaluator._load_split = cached
    orig_predict=evaluator._predict
    evaluator._predict=lambda model,X,batch_size,device: orig_predict(model,legacy._compute_sdf_features(X,cfg.input_features),batch_size,device)
    def raw_case_rows(model, split):
        """Additional SSE accounting using unchanged legacy raw restoration."""
        data=cached(split,seed)
        preds=evaluator._predict(model,data['X'],4,torch.device('cuda'))
        by_case={}
        for i,idx in enumerate(data['patch_to_case'].tolist()):
            by_case.setdefault(names[idx],[]).append(i)
        formatter=evaluator._load_formatter()
        rows={}
        for case,ids in by_case.items():
            truth,angle=bundle['raw_cases'][case]
            r2,mae,t,p=_per_case_r2(case,truth,angle,ids,preds,formatter,640)
            assert t is not None and np.isfinite(r2) and len(t)>0,case
            sq=float(np.sum((t-p)**2))
            rows[case]={'r2':float(r2),'rmse':float(np.sqrt(sq/len(t))),
                        'n':int(len(t)),'sse':sq,'mae':float(mae)}
        return rows
    cls = legacy._resolve_model_cls(cfg)
    model = cls(**legacy._model_kwargs_for_cfg(cls,cfg)).cuda()
    scores=[]
    checkpoints=sorted(out.glob('checkpoint_ep*.pt'))
    assert len(checkpoints)==20, len(checkpoints)
    for ckpt in checkpoints:
        state=torch.load(ckpt,map_location='cpu',weights_only=False)
        epoch=int(state['epoch'])
        model.load_state_dict(state['model_state_dict'])
        val=evaluator.evaluate(model,split='val',seed=seed,device=torch.device('cuda'))
        assert val['n_cases_evaluated']==34 and val['n_fail']==0
        scores.append({'epoch':epoch,'val_r2_median':val['r2_median']})
        (out/'checkpoint_selection.json').write_text(json.dumps(scores,indent=2))
        print('VAL',out.name,epoch,val['r2_median'],flush=True)
    assert [r['epoch'] for r in scores]==list(range(50,1001,50))
    winner=max(scores,key=lambda r:(r['val_r2_median'],-r['epoch']))
    model.load_state_dict(torch.load(out/f"checkpoint_ep{winner['epoch']:04d}.pt",map_location='cpu',weights_only=False)['model_state_dict'])
    original_save=torch.save
    original_save(model.state_dict(),out/'model_selected_val_r2.pt')
    holdout=evaluator.evaluate(model,split='holdout',seed=seed,device=torch.device('cuda'))
    assert holdout['n_cases_evaluated']==100 and holdout['n_fail']==0
    val_rows=raw_case_rows(model,'val')
    test_rows=raw_case_rows(model,'holdout')
    assert len(val_rows)==34 and len(test_rows)==100
    assert abs(float(np.median([r['r2'] for r in val_rows.values()]))-winner['val_r2_median'])<1e-9
    assert abs(float(np.median([r['r2'] for r in test_rows.values()]))-holdout['r2_median'])<1e-9
    result={'seed':seed,'size':out.name,'epoch':winner['epoch'],'val_r2_median':winner['val_r2_median'],
            'test_r2_median':holdout['r2_median'],'test_r2_by_case':holdout['per_case_r2'],
            'val':val_rows,'test':test_rows,
            'train_metrics':metrics,'elapsed_seconds':time.monotonic()-start if start is not None else None}
    (out/'summary.json').write_text(json.dumps(result,indent=2,default=str))
    print('S2_DONE',out.name,winner,flush=True)


if __name__=='__main__':
    main()
