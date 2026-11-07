import sys,torch
sys.path.insert(0,'.')
from swe_nl_pde import SWE_NL
from train_utils.losses import physicsnemo_fourier, pino_loss_swe_nonlin, physicsnemo_fdm_swe_nonlin
node=SWE_NL(g=1.0,nu=0.002).make_computations()
d='cuda'
for b in (1,2,3):
    s=torch.randn(b,128,128,101,3,device=d,requires_grad=True)
    h,u,v=s[...,0],s[...,1],s[...,2]
    Dh,Du,Dv=physicsnemo_fdm_swe_nonlin(h,u,v,node,device=d)
    l=physicsnemo_fourier(s,node); l.backward()
    print(f'batch={b} Dh.shape={tuple(Dh.shape)} physicsnemo_loss={l.item()} grad_finite={torch.isfinite(s.grad).all().item()} grad_abs_max={s.grad.abs().max().item()}',flush=True)
s=torch.randn(1,128,128,101,3,device=d)
print('batch=1 original_loss',pino_loss_swe_nonlin(s,g=1.0,nu=0.002).item(),flush=True)
