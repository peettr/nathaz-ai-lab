#!/usr/bin/env python3
"""Freeze a closed Case A STL by lowering only its bottom vertices."""
import argparse, hashlib, json, math, struct
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('target'); a=p.parse_args()
src=Path(a.source).read_bytes(); n=struct.unpack_from('<I',src,80)[0]
assert len(src)==84+50*n and n==24
b=bytearray(src); counts={}; changed=0
for i in range(n):
    off=84+50*i
    for j in range(3):
        zoff=off+12+12*j+8
        z=struct.unpack_from('<f',b,zoff)[0]; counts[z]=counts.get(z,0)+1
        if z==-20.0:
            struct.pack_into('<f',b,zoff,-30.0); changed+=1
        else: assert z in (0.,64.), (i,j,z)
assert changed>0 and counts.get(-20.)>0
# Invariant: apart from lower z components, every source byte is unchanged.
for i in range(n):
    for j in range(3):
        off=84+50*i+12+12*j+8
        z0=struct.unpack_from('<f',src,off)[0]
        assert struct.unpack_from('<f',b,off)[0]==(-30. if z0==-20. else z0)
        b[off:off+4]=src[off:off+4]
assert b==src
out=bytearray(src)
for i in range(n):
    for j in range(3):
        off=84+50*i+12+12*j+8
        if struct.unpack_from('<f',src,off)[0]==-20.:struct.pack_into('<f',out,off,-30.)
target=Path(a.target); assert not target.exists(); target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
print(json.dumps({'source_sha256':hashlib.sha256(src).hexdigest(),'new_sha256':hashlib.sha256(out).hexdigest(),'triangles':n,'bottom_vertices_changed':changed,'source_z_vertex_counts':counts,'new_bounds_z':[-30,64],'target':str(target)},indent=2))
