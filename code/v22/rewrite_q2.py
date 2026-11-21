#!/usr/bin/env python3
"""Akron v2.2: change ONLY the data payload of SPECHUMD at 200100 Pa.
Read/write WPS intermediate unformatted big-endian Fortran records; no v2.1 writes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import numpy as np

GROUPS = ('G06','P06','G24','P24','G48','P48','G72','P72')
FIELDS = ('GHT','TT','UU','VV','SPECHUMD')
SOURCE = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_akron/drivers_v21_final')
TARGET = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_akron/v22_final')

def records(path):
    with open(path, 'rb') as f:
        while True:
            prefix = f.read(4)
            if not prefix: return
            if len(prefix) != 4: raise ValueError(f'truncated prefix {path}')
            n, = struct.unpack('>I', prefix)
            if n > 500000000: raise ValueError('absurd record length')
            data = f.read(n); suffix = f.read(4)
            if len(data) != n or suffix != prefix: raise ValueError(f'bad record length {path}')
            yield prefix + data + suffix, data

def slabs(path):
    recs = iter(records(path))
    while True:
        try: version, vd = next(recs)
        except StopIteration: return
        if len(vd) != 4 or struct.unpack('>I',vd)[0] != 5: raise ValueError('not WPS version 5')
        header, h = next(recs); projection, _ = next(recs)
        wind, _ = next(recs); datarec, data = next(recs)
        if len(h) != 156: raise ValueError(f'header size {len(h)}')
        field = h[60:69].decode('ascii').strip()
        units = h[69:94].decode('ascii').strip()
        level, nx, ny, iproj = struct.unpack('>fiii', h[140:156])
        if len(data) != nx*ny*4: raise ValueError('array size mismatch')
        yield (version, header, projection, wind, datarec), (field,units,int(round(level)),nx,ny,iproj)

def payload(raw): return raw[4:-4]

def array(raw, nx, ny):
    return np.frombuffer(payload(raw), dtype='>f4').reshape((ny,nx))

def haversine_mask(nx, ny, projection):
    # WPS SWCORNER: 8-char name; float lat, lon, dlat, dlon, earth radius
    proj = payload(projection)
    if proj[:8] != b'SWCORNER': raise ValueError('unexpected projection')
    lat0,lon0,dlat,dlon = struct.unpack('>ffff',proj[8:24])
    latitude = lat0 + np.arange(ny)[:,None]*dlat
    longitude = lon0 + np.arange(nx)[None,:]*dlon
    a = np.sin(np.deg2rad(latitude-40.17563)/2)**2 + np.cos(np.deg2rad(latitude))*math.cos(math.radians(40.17563))*np.sin(np.deg2rad(longitude+103.22203)/2)**2
    return (6371*2*np.arcsin(np.sqrt(a))) <= 300, (lat0,lon0,dlat,dlon)

def describe(path):
    fields = {}; layers = {}
    for recs, meta in slabs(path):
        name,units,level,nx,ny,_ = meta
        ar = array(recs[4],nx,ny)
        if not np.all(np.isfinite(ar)): raise ValueError(f'nonfinite {name} {level}')
        entry = fields.setdefault(name, {'units': units, 'levels_pa':[], 'min':float('inf'), 'max':float('-inf')})
        if entry['units'] != units: raise ValueError('units mismatch')
        entry['levels_pa'].append(level)
        entry['min'] = min(entry['min'],float(ar.min()))
        entry['max'] = max(entry['max'],float(ar.max()))
        layers.setdefault(name,set()).add(level)
    return {'file':str(path), 'records':sum(len(v) for v in layers.values()), 'fields':fields,
            'complete_pressure_levels_pa':sorted(set.intersection(*(layers[k] - {200100} for k in FIELDS)),reverse=True)}

def transform(src, dst):
    entries = list(slabs(src))
    seen = {k:set() for k in FIELDS}
    hgt = {}; q = {}; soil = None; original_q2 = None; q2_index = None
    shape = None; projection = None
    for i,(recs,meta) in enumerate(entries):
        name, units, level, nx,ny,_ = meta
        if shape is None: shape = nx,ny; projection = recs[2]
        if shape != (nx,ny) or recs[2] != projection: raise ValueError('grid varies within file')
        if name in seen and level != 200100:
            if level in seen[name]: raise ValueError('duplicate level')
            seen[name].add(level)
            if name in ('GHT','SPECHUMD'):
                (hgt if name=='GHT' else q)[level] = array(recs[4],nx,ny).copy()
        if name=='SOILHGT' and level==200100: soil=array(recs[4],nx,ny).copy()
        if name=='SPECHUMD' and level==200100:
            if q2_index is not None: raise ValueError('duplicate Q2')
            q2_index=i; original_q2=array(recs[4],nx,ny).copy()
    if soil is None or q2_index is None: raise ValueError('missing SOILHGT or Q2')
    levels = sorted(set.intersection(*(seen[k] for k in FIELDS)),reverse=True)
    if not levels or any(l not in hgt or l not in q for l in levels): raise ValueError('incomplete level')
    new = np.full((ny,nx),np.nan,dtype=np.float32)
    used = np.zeros((ny,nx),dtype=bool)
    counts = {}
    for lev in levels:
        eligible = ~used & (hgt[lev] > soil) & np.isfinite(hgt[lev]) & np.isfinite(q[lev])
        new[eligible] = q[lev][eligible]
        used |= eligible
        counts[str(lev)] = int(eligible.sum())
    if not np.all(used): raise ValueError(f'no above-ground complete level: {int((~used).sum())} cells')
    mask, grid = haversine_mask(nx,ny,projection)
    if mask.shape != new.shape or not np.any(mask): raise ValueError('KAKO region not on grid')
    delta = (new[mask].astype(np.float64)-original_q2[mask].astype(np.float64))*1000
    qbytes = new.astype('>f4').tobytes()
    old = entries[q2_index][0][4]
    if len(qbytes) != len(old)-8: raise ValueError('Q2 payload length changed')
    newrecord = old[:4]+qbytes+old[-4:]
    # Exclusive creation: never overwrite results, partial file remains explicit on failure.
    with open(dst,'xb') as out:
        for i,(recs,_) in enumerate(entries):
            for j,r in enumerate(recs): out.write(newrecord if i==q2_index and j==4 else r)
        out.flush(); os.fsync(out.fileno())
    # Read-back compares every raw record, including every header and original non-Q2 payload.
    nr=list(slabs(dst))
    if len(nr)!=len(entries): raise ValueError('record count changed')
    changes=0
    for i,((oldr,oldmeta),(newr,newmeta)) in enumerate(zip(entries,nr)):
        if oldmeta!=newmeta: raise ValueError('record metadata changed')
        for j,(a,b) in enumerate(zip(oldr,newr)):
            if i==q2_index and j==4:
                if a[:4]!=b[:4] or a[-4:]!=b[-4:]: raise ValueError('Q2 framing changed')
                changes+=1
            elif a!=b: raise ValueError(f'non-Q2 record changed {i} {j}')
    if changes!=1 or not np.array_equal(array(nr[q2_index][0][4],nx,ny),new): raise ValueError('Q2 readback mismatch')
    return {'file':str(dst.relative_to(TARGET)), 'records':len(entries), 'changed_payloads':changes,
            'complete_levels_pa':levels,'selected_levels_cell_counts':counts, 'grid':grid,
            'KAKO_300km_cells':int(mask.sum()), 'KAKO_300km_mean_delta_g_kg':float(delta.mean()),
            'KAKO_300km_max_abs_delta_g_kg':float(np.max(np.abs(delta))),
            'Q2_min_kg_kg':float(new.min()),'Q2_max_kg_kg':float(new.max()),
            'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}

def main():
    global TARGET
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,default=SOURCE);parser.add_argument('--target',type=Path,default=TARGET)
    a=parser.parse_args()
    TARGET=a.target
    if a.target.exists(): raise SystemExit('refuse existing target root')
    sources={g:sorted(p for p in (a.source/g).iterdir() if p.is_file()) for g in GROUPS}
    if [len(sources[g]) for g in GROUPS] != [3,3,6,6,10,10,14,14]: raise ValueError('unexpected source counts')
    a.target.mkdir(parents=True)
    report={'source':str(a.source),'target':str(a.target),'resource_rule':'v2.2 hypothesis; lowest complete pressure level with GHT > SOILHGT', 'files':[], 'readback':{}}
    try:
        for g in GROUPS:
            (a.target/g).mkdir()
            for p in sources[g]:
                result=transform(p,a.target/g/p.name)
                report['files'].append(result)
                print(json.dumps({'done':result['file'],'cells':result['KAKO_300km_cells'],'mean_g_kg':result['KAKO_300km_mean_delta_g_kg']}),flush=True)
            report['readback'][g]={'first':describe(a.target/g/sources[g][0].name), 'last':describe(a.target/g/sources[g][-1].name)}
        with open(a.target/'SHA256SUMS','x') as f:
            for r in report['files']: f.write(r['sha256']+'  '+r['file']+'\n')
        with open(a.target/'READBACK_v22.json','x') as f: json.dump(report,f,indent=2,ensure_ascii=False)
        print('COMPLETE 66 files',flush=True)
    except Exception:
        with open(a.target/'INCOMPLETE_ERROR.txt','x') as f: f.write('Job failed; do not use this output; see stderr. Preserve partial results.\n')
        raise

if __name__=='__main__': main()
