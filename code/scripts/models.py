import numpy as np,torch,time,json,sys
from physicsnemo.models.transolver import Transolver
from physicsnemo.models.fno import FNO
from common import *
dev='cuda'
def tr_model(k=64,h=128): return Transolver(functional_dim=k,out_dim=1,embedding_dim=6,n_layers=4,n_hidden=h,dropout=0.0,n_head=4,slice_num=32,unified_pos=False,structured_shape=None,use_te=False).to(dev)
def fno_model(): return FNO(in_channels=75,out_channels=8040,dimension=1,latent_channels=64,num_fno_layers=4,num_fno_modes=16,padding=8,decoder_layers=1,decoder_layer_size=64).to(dev)
def tr_pred(m,F,E,bs=16):
    out=[]
    with torch.no_grad(), torch.autocast('cuda',dtype=torch.bfloat16):
        for i in range(0,len(F),bs):
            f=F[i:i+bs].to(dev); fx=f[:,None,:].expand(-1,E.shape[0],-1); e=E[None].expand(len(f),-1,-1)
            out.append(m(fx,embedding=e)[...,0].float().cpu())
    return torch.cat(out).numpy()
def fno_pred(m,S,bs=32):
    out=[]
    with torch.no_grad():
        for i in range(0,len(S),bs): out.append(m(S[i:i+bs].to(dev))[:,:,-1].float().cpu())
    return torch.cat(out).numpy()
