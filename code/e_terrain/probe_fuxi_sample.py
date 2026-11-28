import numpy as np
p='/content/e_terrain/fuxi_official/fuxicfd-model/inference_example/data/inputs.npz'
z=np.load(p,allow_pickle=True)
print('keys',z.files)
for k in z.files:print(k,z[k].shape,z[k].dtype,'minmax',np.nanmin(z[k]) if z[k].dtype.kind in 'fiu' else '',np.nanmax(z[k]) if z[k].dtype.kind in 'fiu' else '')
p='/content/e_terrain/fuxi_official_sample_prediction.npz'
z=np.load(p);print('pred_keys',[(k,z[k].shape) for k in z.files])
