"""Numerical recreation of the on-the-fly NeuralGCM-to-HRRR indices."""
import os,sys,pathlib,json,numpy as np
os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';os.environ['XLA_PYTHON_CLIENT_MEM_FRACTION']='.30'
P=pathlib.Path('/content/l264diag04');T=P/'texas';R=P/'AERO_ODE';sys.path.insert(0,str(R/'AERO_AIR_WD'))
from AERO_ODE_v3 import NeuralGCMInference
ng=NeuralGCMInference(str(R/'shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl'),inner_steps=1,outer_steps=73)
meta=json.loads((T/'window.json').read_text());y,x=meta['west_offset'];h,w=meta['shape']
ref=R/'AERO_AIR_WD/Hrrr_rb/data'
la=np.load(ref/'hrrr_west_lat.npy').T;lo=np.load(ref/'hrrr_west_lon.npy').T
ny=np.load(T/'noaa_lat.npy',mmap_mode='r')[y:y+h,x:x+w].T
nx=np.load(T/'noaa_lon.npy',mmap_mode='r')[y:y+h,x:x+w].T
idx_a=np.asarray(ng._compute_interp_indices(lo,la));idx_b=np.asarray(ng._compute_interp_indices(nx,ny))
import h5py
with h5py.File(ref/'west_geo_interpolate.h5') as f:shape=list(f['fields'].shape)
res={'author_code':'AERO_AIR_WD/AERO_ODE_v3.py:151-177, 207-214; indices calculated on demand',
     'west_geo_interpolate_h5_fields_shape':shape,'west_geo_file_role':'terrain/static input, not a saved interpolation table',
     'idx_shape':list(idx_a.shape),'original_vs_reconstructed_max_abs_index':float(abs(idx_a-idx_b).max()),
     'original_vs_reconstructed_mean_abs_index':float(abs(idx_a-idx_b).mean()),
     'original_vs_reconstructed_exact_fraction':float(np.mean(idx_a==idx_b)),
     'source_lat_shape':list(np.shape(ng.model_lat)),'source_lon_shape':list(np.shape(ng.model_lon))}
(T/'interpolation_diag.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2),flush=True)
