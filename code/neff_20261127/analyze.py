#!/usr/bin/env python3
"""Read S2 CSV on stdin, R1 and public tap map read-only; post-hoc spatial sensitivity."""
import csv, io, json, random, statistics as st, sys, hashlib, math
from pathlib import Path
ROOT=Path('./')
R1=ROOT/'26_Quick_Trials/06_Logs/L26.23/R1_post_receipt_1757227/out/per_tap_main.csv'
COORD=ROOT/'41_Second_Lab/L41.10_五个核心难点/L41.10b_LES风压模拟/06_Work/scripts/zones_taps_090.csv'
raw=sys.stdin.buffer.read()
assert hashlib.sha256(raw).hexdigest()=='bd42b2bf24c8be0c661f46f4b3e9620f674b00d150034357de44146662760072'
s2={int(r['tap_id']):r for r in csv.DictReader(io.StringIO(raw.decode()))}
r1={int(r['tap_id']):r for r in csv.DictReader(R1.open())}
coords={int(r['tap_id']):r for r in csv.DictReader(COORD.open())}
assert len(s2)==len(r1)==len(coords)==360 and s2.keys()==r1.keys()==coords.keys()
IDS=sorted(i for i in s2 if s2[i]['zone']=='side_separated')
assert len(IDS)==216
# A rectangular block is 2 adjacent heights x 3 adjacent streamwise taps, separately per face.
# 12 heights x 9 taps x 2 faces => 36 blocks of 6 taps.
# Observed x,z sorted, not inferred from tap IDs. Face 1 and face 3 remain separate.
blocks={}; layout={}
for face in (1,3):
    sub=[i for i in IDS if int(coords[i]['face'])==face]
    x=sorted({round(float(coords[i]['x_m']),5) for i in sub})
    z=sorted({round(float(coords[i]['z_m']),5) for i in sub})
    assert len(x)==9 and len(z)==12 and len(sub)==108
    for i in sub:
        xi=x.index(round(float(coords[i]['x_m']),5)); zi=z.index(round(float(coords[i]['z_m']),5))
        blocks.setdefault((face,zi//2,xi//3),[]).append(i)
assert len(blocks)==36 and all(len(v)==6 for v in blocks.values())
blocklist=list(blocks.values())
def q(x,p):
    x=sorted(x); u=(len(x)-1)*p; a=int(u); b=min(a+1,len(x)-1); return x[a]+(u-a)*(x[b]-x[a])
def bs_iid(vals,B=6000,seed=4101009):
    rr=random.Random(seed); n=len(vals)
    return [st.median(vals[rr.randrange(n)] for _ in range(n)) for _ in range(B)]
def bs_block(vals,B=6000,seed=4101009):
    rr=random.Random(seed); keys=list(blocks)
    return [st.median(vals[i] for k in (keys[rr.randrange(len(keys))] for _ in keys) for i in blocks[k]) for _ in range(B)]
def one(metric,keys=IDS):
    d={i:float(r1[i][f'neg_{metric}_LES'])-float(s2[i][f'neg_{metric}_LES']) for i in keys}
    v=list(d.values()); a=bs_iid(v); b=bs_block(d)
    ci0=[q(a,.05),q(a,.95)];ci1=[q(b,.05),q(b,.95)]
    w0=ci0[1]-ci0[0]; w1=ci1[1]-ci1[0]
    neff=len(v)*(w0/w1)**2 if w1 else None
    # alternating-face/row blocks preserve paired tap differences, not independent inflow replicates
    return {'median':st.median(v),'iid_CI90':ci0,'spatial_CI90':ci1,'iid_width':w0,'spatial_width':w1,'n_eff_median_equivalent':neff,
      'face_medians':{str(face):st.median(d[i] for i in keys if int(coords[i]['face'])==face) for face in (1,3)} if keys==IDS else {}}
out={'source_s2_sha256':hashlib.sha256(raw).hexdigest(),'source_r1_sha256':hashlib.sha256(R1.read_bytes()).hexdigest(),'source_coords_sha256':hashlib.sha256(COORD.read_bytes()).hexdigest(),
  'method':'36 fixed x-z blocks, each 2 neighboring heights x 3 neighboring x positions x 1 face (6 taps); draw 36 blocks with replacement, paired R1-S2 tap differences kept; median 6000 draws seed 4101009. n_eff = 216*(IID 90% interval width / block 90% interval width)^2; post-hoc precision-equivalent only, not independent CFD runs.',
  'block_count':len(blocks),'block_size':6,'side':{p:one(p) for p in ('50','90')}}
# Windward face is a flow-difference diagnostic, not a clean upstream inlet measurement.
for p in ('50','90'):
    ids=[i for i in s2 if s2[i]['zone']=='windward']
    d=[float(r1[i][f'neg_{p}_LES'])-float(s2[i][f'neg_{p}_LES']) for i in ids]
    b=bs_iid(d)
    out.setdefault('windward_proxy',{})[p]={'n':len(ids),'median':st.median(d),'CI90_iid':[q(b,.05),q(b,.95)],'caveat':'windward pressure tap, not upstream inlet; both inflow and wall treatment may affect it'}
# Spatial block-size sensitivity: preserve each face and contiguous x-z neighborhoods.
for bh,bx in ((1,3),(2,3),(3,3),(3,9)):
    til={}
    for face in (1,3):
        sub=[i for i in IDS if int(coords[i]['face'])==face]
        x=sorted({round(float(coords[i]['x_m']),5) for i in sub})
        z=sorted({round(float(coords[i]['z_m']),5) for i in sub})
        for i in sub:
            xi=x.index(round(float(coords[i]['x_m']),5));zi=z.index(round(float(coords[i]['z_m']),5))
            til.setdefault((face,zi//bh,xi//bx),[]).append(i)
    assert sum(map(len,til.values()))==216 and len({i for v in til.values() for i in v})==216
    row={'tile':f'{bh} height x {bx} x, one face','blocks':len(til),'per_block':bh*bx}
    for p in ('50','90'):
        d={i:float(r1[i][f'neg_{p}_LES'])-float(s2[i][f'neg_{p}_LES']) for i in IDS}
        rr=random.Random(4101009); keys=list(til)
        draw=[st.median(d[i] for k in (keys[rr.randrange(len(keys))] for _ in keys) for i in til[k]) for _ in range(6000)]
        lo,hi=q(draw,.05),q(draw,.95)
        iid=out['side'][p]['iid_width']; row[p]={'CI90':[lo,hi],'n_eff':216*(iid/(hi-lo))**2}
    out.setdefault('sensitivity',[]).append(row)
print(json.dumps(out,indent=2,ensure_ascii=False))
