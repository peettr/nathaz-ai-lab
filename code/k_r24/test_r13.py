#!/usr/bin/env python3
"""Tiny WPS-v5 synthetic regression, no meteorological computation on 工作站."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import numpy as np

spec = importlib.util.spec_from_file_location('r13', Path(__file__).with_name('build_r13.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def rec(x):
    return struct.pack('>I',len(x))+x+struct.pack('>I',len(x))

def slab(field, level, values):
    h = bytearray(156)
    h[60:69] = field.ljust(9).encode()
    h[69:94] = b'unit'.ljust(25)
    h[140:156] = struct.pack('>fiii',float(level),2,1,0)
    return b''.join(rec(x) for x in (struct.pack('>I',5),bytes(h),b'projection',b'wind',np.array(values,dtype='>f4').tobytes()))

with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
    src, out = Path(d)/'src', Path(d)/'out'
    chunks = []
    # Real 31-level sequence from archived readback: exact duplicate-free levels.
    levels = [100000,97500,95000,92500,90000,85000,80000,75000,70000,65000,60000,55000,50000,45000,40000,35000,30000,25000,20000,15000,10000,7000,5000,3000,2000,1000,700,500,300,200,100]
    for lev in levels:
        for field in r.FIELDS:
            vals = [float(100000-lev)/100, float(100000-lev)/100]
            if field == 'SPECHUMD': vals = [lev/1e8,lev/1e8]
            chunks.append(slab(field, lev, vals))
    chunks += [slab('SOILHGT',200100,[10,90]),slab('PMSL',201300,[1,2]),slab('SPECHUMD',200100,[0.1,0.2]),slab('TT',200100,[3,4])]
    src.write_bytes(b''.join(chunks))
    report = r.transform(src,out)
    assert report['output_slabs'] == len(chunks)-90
    assert report['selected_level_cells']['100000'] == 0
    assert report['selected_level_cells']['92500'] == 1
    assert report['selected_level_cells']['85000'] == 1
    assert report['surface_slabs_preserved'] == 4
    assert [meta[0] for _,meta in r.slabs(out)][-4:] == ['SOILHGT','PMSL','SPECHUMD','TT']
    try: r.transform(src,out)
    except FileExistsError: pass
    else: raise AssertionError('overwrite was not refused')
    print('PASS synthetic 31-to-13, Q2 selected per cell, surface order, exclusive output')
