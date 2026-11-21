#!/usr/bin/env python3
"""Fetch Francine with unchanged H2 expanded grid construction, new filenames only."""
import os, inspect
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import run_h2_expanded as h

if __name__ == '__main__':
    # The existing event function is reused verbatim except the output suffix.
    source=inspect.getsource(h.get_grid)
    assert source.count('_expanded') == 5, source.count('_expanded')
    source=source.replace('_expanded','_h2f')
    scope=dict(vars(h));exec(compile(source,str(Path(__file__)),'exec'),scope)
    h.STATES['FRANCINE']='LA,MS'
    h.old.CANDIDATES['FRANCINE']=('2024','202409112200','LA,MS')
    hurdat=h.old.parse_hurdat()
    assert 'FRANCINE' in hurdat
    grid=scope['get_grid']('FRANCINE',hurdat,h.b.get_land())
    assert grid.hour.nunique()>=20 and grid.station.nunique()>=8
    print('FRANCINE',grid.shape,grid.station.nunique(),grid.hour.min(),grid.hour.max(),flush=True)
