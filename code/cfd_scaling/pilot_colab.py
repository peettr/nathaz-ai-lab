"""Development-only smoke: 524 valid UrbanTALES cases, never read test targets/metrics."""
import os, time, json, ast
from pathlib import Path
import numpy as np
source=Path('/content/train_colab.py').read_text()
prefix=source.split("rec={'dataset':",1)[0]
prefix=prefix.replace("assert H.shape==(538,160,160) and all(M[ix[s]].any() for s in names),'extraction must be complete'", "assert H.shape==(538,160,160) and sum(M[i].any() for i in range(len(names)))==524")
prefix=prefix.replace("val=np.array([ix[c] for c in S['val_cases']]);test=np.array([ix[c] for c in S['test_cases']]); typ=S['type_by_case']", "val=np.array([ix[c] for c in S['val_cases'] if M[ix[c]].any()]);test=val; typ=S['type_by_case']")
prefix=prefix.replace('for epoch in range(1,61):','for epoch in range(1,5):')
exec(compile(prefix,'/content/train_colab.py','exec'))
print('PILOT: valid',sum(m.any() for m in M),'development_validation',len(val),'cuda',torch.cuda.get_device_name(0),flush=True)
seed=17
ids=np.array([ix[c] for c in S['seeds'][str(seed)]['400'] if M[ix[c]].any()][:50])
assert len(ids)==50 and all(M[i].any() for i in ids), 'pilot must have 50 valid training cases'
t=time.monotonic(); preds=baseline(ids)
assert set(preds)=={'B0','B1','B2'} and all(set(p)==set(val) for p in preds.values())
print('BASELINES_OK',round(time.monotonic()-t,2),{k:float(np.mean([p[j][M[j]].mean() for j in val])) for k,p in preds.items()},flush=True)
t=time.monotonic(); pred,hist=train_unet(ids,seed)
print('UNET_OK',len(hist),'validation_steps',round(time.monotonic()-t,2),'validation_losses',hist,flush=True)
print('PILOT_COMPLETE_NOT_SCIENTIFIC_EVIDENCE',flush=True)
