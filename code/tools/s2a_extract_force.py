"""从 L30.2f 裸塔 OpenFAST 输出（只读临时副本）抽模态力与塔顶侧向位移。用法: python3 -I s2a_extract_force.py <outb_dir> <L30_L1_dir> <L30_rl_base_dir> <out.npz>"""
import sys,glob,os,numpy as np
d,l1,rb,out=sys.argv[1:5];sys.path[:0]=[l1,rb]
from reduce_pairs import read_outb
from l1_active_rom import modal_force,DT
F=[];Y=[];S=[]
for p in sorted(glob.glob(os.path.join(d,'bare_*.outb'))):
    from pathlib import Path;names,data,t0,dt,n=read_outb(Path(p));assert abs(dt-DT)<1e-9 and n==12001
    f=data[:,names.index('RtAeroFyi')-1];m=data[:,names.index('RtAeroMxi')-1];F.append(modal_force(f,m));Y.append(data[:,names.index('TTDspSS')-1]);S.append(int(os.path.basename(p)[5:9]))
np.savez_compressed(out,force=np.array(F),ttdsp=np.array(Y),seeds=np.array(S),dt=DT);print('saved',out,np.array(F).shape)
