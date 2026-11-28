#!/usr/bin/env python3
"""Host-only A3 indexing fixture; not native flags/device acceptance."""
import json
from pathlib import Path

NX, NY = 256, 128
S, E = 1, 2

def count(flags):
    valid = 0
    bad = []
    for y in range(NY):
        for x in range(NX):
            xp, xm = (x + 1) % NX, (x - 1) % NX
            yp, ym = (y + 1) % NY, (y - 1) % NY
            ok = (flags[0][y][x] & (S | E)) == S
            ok &= (flags[1][y][x] & (S | E)) == 0
            ok &= (flags[2][y][x] & (S | E)) == 0
            ok &= all((flags[1][yy][xx] & (S | E)) == 0 for xx, yy in ((xp,y),(xm,y),(x,yp),(x,ym)))
            ok &= all((flags[0][yy][xx] & (S | E)) == S for xx, yy in ((xp,y),(xm,y),(x,yp),(x,ym)))
            if ok: valid += 1
            else: bad.append([x,y])
    return valid, bad

flags = [[[S if z == 0 else 0 for x in range(NX)] for y in range(NY)] for z in range(3)]
clean, bad = count(flags)
assert clean == NX*NY and not bad
flags[0][0][0] = 0
corrupt, bad = count(flags)
assert corrupt == clean - 5 and sorted(bad) == sorted([[0,0],[1,0],[NX-1,0],[0,1],[0,NY-1]])
print(json.dumps({'fixture': 'host-only synthetic flags', 'all_eligible': clean, 'one_bad_ground_cell': {'eligible': corrupt, 'rejected_columns': bad}, 'negative_detected': True}, ensure_ascii=False))
