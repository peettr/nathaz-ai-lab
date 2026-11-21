from earth2studio.data import HRRR,HRRR_FX
from earth2studio.lexicon.hrrr import HRRRLexicon,HRRRFXLexicon
import datetime as dt,numpy as np
print('lex',HRRRLexicon['z'],HRRRFXLexicon['Z1hl'])
t=dt.datetime(2023,2,26,21)
a=HRRR(verbose=False)([t],['z']);b=HRRR_FX(verbose=False)([t],[dt.timedelta(hours=1)],['Z1hl'])
print('terrain',a.min().item(),a.max().item(),'Z1',b.min().item(),b.max().item(),'shapes',a.shape,b.shape,'at',a.values[0,0,600,900],b.values[0,0,0,600,900],flush=True)
