"""Disposable Colab installation; pin the two decisive upstream versions."""
import pathlib, subprocess, sys, traceback
P=pathlib.Path('/content/l264h100');P.mkdir(exist_ok=True)
def run(*a):print('INSTALL',a,flush=True);subprocess.run(a,check=True)
try:
    run(sys.executable,'-m','pip','install','--no-cache-dir','torch==2.4.0+cu121','torchvision==0.19.0+cu121','--index-url','https://download.pytorch.org/whl/cu121')
    run(sys.executable,'-m','pip','install','--no-cache-dir','jax[cuda12]==0.4.29','jaxlib==0.4.29','numpy==1.26.4','ml-dtypes==0.5.3','xarray==2025.6.1','netCDF4==1.7.2','h5py==3.12.1','matplotlib==3.10.0','scipy==1.15.3','dm-haiku==0.0.14','dinosaur==1.3.4','neuralgcm==1.0.0','optax==0.2.5','tensorflow-probability==0.25.0','zarr==2.18.3','numcodecs==0.13.1','pandas==2.3.1','dask==2025.7.0','gin-config==0.5.0','grain==0.2.13','cartopy==0.25.0','cf-xarray==0.10.6','tensorstore==0.1.76')
    root=P/'AERO_ODE'/'physics_core'
    run(sys.executable,'-m','pip','install','--no-deps','-e',str(root/'dinosaur-main'/'dinosaur-main'),'-e',str(root/'neuralgcm-main'))
    run(sys.executable,'-c',"import torch,jax; print('VERSIONS',torch.__version__,jax.__version__); print('GPU',torch.cuda.get_device_name(0),jax.devices('gpu'))")
    (P/'install.done').write_text('ok\n')
except BaseException:
    (P/'install.failed').write_text(traceback.format_exc());traceback.print_exc();raise
