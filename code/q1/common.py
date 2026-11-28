"""Frozen Q1 targets, command coordinates, measurements and scoring definitions."""
import json, sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'object'))
from plant import Params,Plant,Z,commands,metrics,score
ZREF=.198
LO=np.array([0]+[-17]*8+[0]*8+[.3]*8+[0]*2,float)
HI=np.array([17]+[20]*8+[8]*8+[50]*8+[.16]*2,float)
BASE=np.array([6]+[6]*8+[1]*8+[3]*8+[.01]*2,float)
# Event number follows Mokhtar 2024 Table 1, PDF p.5 (columns ordered by Lux).
EVENTS=[(f'EVT{i+1:02d}',(11,9,7)[i%3],(.15,.20,.30)[i%3],(1.,3.,5.,7.)[i//3],(8,5,3)[i%3]) for i in range(12)]
TUNING=[('TUNE01',10,.18,2.,6),('TUNE02',8,.25,4.,6)]

def target(event):
    _,inv_alpha,iu,lux,inv_gamma=event
    z=Z/ZREF
    return np.stack((6*z**(1/inv_alpha),iu*z**(-1/6),lux*z**(1/inv_gamma)))

def errors(observation,event):
    t=target(event)
    return np.array([
        np.sqrt(np.mean(((observation['u']-t[0])/6.)**2)),
        np.sqrt(np.mean(((observation['Iu']-t[1])/t[1])**2)),
        np.sqrt(np.mean(((observation['Lux']-t[2])/t[2])**2))])

def vector_command(x,p,duration,seed):
    x=np.clip(np.asarray(x,float),LO,HI)
    return commands(p,float(x[0]),x[1:9],x[9:17],x[17:25],x[25:27],duration,seed)

def evaluate(p,x,event,duration=600.,seeds=(1001,),command_seeds=(2001,)):
    x=np.asarray(x,float)
    if x.shape!=(27,):raise ValueError('27 command coordinates required')
    r=score(p,float(x[0]),x[1:9],x[25:27],amplitude=x[9:17],wavelength=x[17:25],duration=duration,seeds=seeds,command_seeds=command_seeds)
    return errors(r,event),r

def members(kind):
    if kind not in ('scoring','tuning'):raise ValueError(kind)
    return json.loads((HERE/'object'/f'{kind}.json').read_text())

def normalized(e):return float(np.mean(np.asarray(e)/[.05,.10,.20]))
