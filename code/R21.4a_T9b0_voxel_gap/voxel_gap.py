#!/usr/bin/env python3.10
"""Read-only T9b-0 voxelized narrow-axis transects; no solver."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

IDS = (31,39,40,47,48,49,50,51,52,55,65,66,69,74,77,79)
UREF = 3.9286416

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def sources(points, widths):
    p=json.loads(Path(points).read_text())
    p={int(row['id']):row for row in p if row['h_wall_m']==2.0}
    with open(widths,newline='') as f:w={int(row['id']):row for row in csv.DictReader(f)}
    assert set(IDS)<=p.keys() and set(IDS)<=w.keys()
    out=[]
    for id in IDS:
        q=p[id];r=w[id]
        wx,wy=(float(r['width_'+axis+'_m']) if r['width_'+axis+'_m'] else math.inf for axis in ('x','y'))
        width=float(r['width_min_m']);axis='x' if wx<=wy else 'y'
        assert math.isclose(width,min(wx,wy),abs_tol=1e-5),(id,width,wx,wy)
        out.append({'id':id,'wall_m':float(r['wall_m']),'width_min_m':width,'axis':axis,
                    'xyz_1m':q['baseline_1m']['xyz_m'],'xyz_0p5m':q['fine']['primary']['xyz_m'],
                    'obs':q['obs'],'delta_ri':(q['fine']['primary']['Su']-q['baseline_1m']['Su'])/UREF})
    return out

def vtk_fluid(path):
    with open(path,'rb') as f:
        lines=[]
        for _ in range(25):
            line=f.readline().decode('ascii').strip();lines.append(line)
            if line.startswith('LOOKUP_TABLE'):break
        offset=f.tell()
    dims=tuple(map(int,next(t for t in lines if t.startswith('DIMENSIONS')).split()[1:]))
    origin=tuple(map(float,next(t for t in lines if t.startswith('ORIGIN')).split()[1:]))
    spacing=tuple(map(float,next(t for t in lines if t.startswith('SPACING')).split()[1:]))
    nx,ny,nz=dims;N=nx*ny*nz
    assert dims==(1000,1000,540) and origin==(0.,0.,-20.) and spacing==(.5,)*3
    raw=np.memmap(path,mode='r',dtype='u1')
    pos=offset+3*N*4 # u_avg
    for name in ('rho_avg','fluid'):
        tag=f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode()
        assert bytes(raw[pos:pos+len(tag)])==tag,(name,pos)
        pos+=len(tag)
        if name=='rho_avg':pos+=N*4
    fluid=np.ndarray((nz,ny,nx),dtype='>f4',buffer=raw,offset=pos)
    assert np.isfinite(fluid[44:46,::100,::100]).all()
    return fluid,{'dims':dims,'origin':origin,'spacing':spacing,'bytes':Path(path).stat().st_size,'fluid_offset':pos}

def transects(entries, planes, dx):
    out=[];n=500 if dx==1 else 1000
    for row in entries:
        x,y,z=row['xyz_1m' if dx==1 else 'xyz_0p5m'];axis=row['axis']
        i=math.floor(x/dx+0.5);j=math.floor(y/dx+0.5)
        assert 0<=i<n and 0<=j<n
        # Desired height is between labels: retain both adjacent native planes.
        k_float=(z+20)/dx;k0=math.floor(k_float+1e-9);ks=(k0,k0+1) if not math.isclose(k_float,k0,abs_tol=1e-8) else (k0,)
        for k in ks:
            line=planes[k][j,:] if axis=='x' else planes[k][:,i]
            assert len(line)==n and np.isfinite(line).all()
            fluid=line>.5;ind=i if axis=='x' else j
            if fluid[ind]:
                lo=ind
                while lo>0 and fluid[lo-1]:lo-=1
                hi=ind
                while hi<n-1 and fluid[hi+1]:hi+=1
                count=hi-lo+1;edge=lo==0 or hi==n-1
            else:lo=hi=None;count=0;edge=False
            out.append({'id':row['id'],'axis':axis,'k':k,'z_label_m':-20+k*dx,'point_index':[i,j],
                        'point_fluid':bool(fluid[ind]),'channel_cells':count,'channel_width_m':count*dx,
                        'left_index':lo,'right_index':hi,'domain_edge_censored':edge,
                        'width_min_m':row['width_min_m'],'narrowing_m':row['width_min_m']-count*dx,
                        'blocked_le_1_cell':count<=1,'xyz_m':[x,y,z]})
    return out

def main():
    a=argparse.ArgumentParser();a.add_argument('--points',required=True);a.add_argument('--widths',required=True)
    a.add_argument('--mode',choices=['local','remote'],required=True);a.add_argument('--thin');a.add_argument('--vtk');a.add_argument('--out',required=True)
    args=a.parse_args();entries=sources(args.points,args.widths)
    if args.mode=='local':
        assert args.thin
        with np.load(args.thin) as npz:
            meta=json.loads(str(npz['metadata'])); assert meta['k_start']==20 and meta['dims']==[500,500,270] and meta['origin']==[0.,0.,-20.]
            fluid=npz['fluid'];planes={k:fluid[k-20] for k in (22,23)}
            results=transects(entries,planes,1.)
        meta={'source':args.thin,'source_sha256':sha(args.thin),'planes':[22,23],'entries':results}
    else:
        assert args.vtk
        fluid,info=vtk_fluid(args.vtk)
        results=transects(entries,{k:fluid[k] for k in (44,45)},.5)
        meta={'source':args.vtk,'vtk_metadata':info,'planes':[44,45],'entries':results}
    assert len(results)==32 and {r['id'] for r in results}==set(IDS)
    out=Path(args.out);assert not out.exists(),f'refuse overwrite: {out}'
    out.write_text(json.dumps(meta,indent=2)+'\n')
    print('VOXEL_DONE',args.mode,len(results),str(out),sha(out),flush=True)
if __name__=='__main__':main()
