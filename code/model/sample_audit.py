"""Read one published training sample's boundary orientation, then delete it."""
import json, os, pathlib
import numpy as np
from huggingface_hub import hf_hub_download
root=pathlib.Path('/content/l26_19_wp')
p=pathlib.Path(hf_hub_download(repo_id='wclw1021/WorldParticle', repo_type='dataset', filename='fancy_fluid/dataset/0/0.npz', local_dir=str(root/'sample'), local_dir_use_symlinks=False))
try:
    with np.load(p, allow_pickle=False) as d:
        print('keys', [(k, d[k].shape, str(d[k].dtype)) for k in d.files], flush=True)
        box=np.asarray(d['box']); normals=np.asarray(d['box_feats'])
        pos=np.asarray(d['position']) if 'position' in d else np.asarray(d['positions'])
        if pos.ndim==3: pos=pos[0]
        lo,hi=box.min(0),box.max(0)
        ctr=(lo+hi)/2
        # A normal at a face points inward iff the dot product with (center-box) is positive.
        mask=np.linalg.norm(normals,axis=1)>0
        dots=np.einsum('ij,ij->i',normals[mask],ctr-box[mask])
        report=dict(box_shape=list(box.shape), normals_shape=list(normals.shape), box_min=lo.tolist(), box_max=hi.tolist(), fluid_shape=list(pos.shape), fluid_min=pos.min(0).tolist(), fluid_max=pos.max(0).tolist(), inward_fraction=float(np.mean(dots>0)), outward_fraction=float(np.mean(dots<0)), normal_mean=normals.mean(0).tolist(), dot_quantiles=np.quantile(dots,[0,.1,.5,.9,1]).tolist())
        print('REPORT',json.dumps(report),flush=True)
        (root/'sample_audit.json').write_text(json.dumps(report,indent=2))
finally:
    p.unlink()
    print('sample_deleted',not p.exists(),flush=True)
