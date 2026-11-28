#!/usr/bin/env python3
"""Read-only bounded VTK 80-point trilinear sampler, T2c coordinates and weights."""
import argparse, hashlib, itertools, json, math, pathlib, struct

SOURCE='/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk'
FINE='/scratch/04448/[用户]/r24_luw/T2b_05m/case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk'
FIELDS=(('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1))
def header(path):
    with path.open('rb') as f:
        lines=[]
        for _ in range(25):
            line=f.readline().decode('ascii').strip(); lines.append(line)
            if line.startswith('LOOKUP_TABLE'): break
        offsets={'u_avg':f.tell()}
        dims=tuple(map(int,next(x for x in lines if x.startswith('DIMENSIONS')).split()[1:]))
        origin=tuple(map(float,next(x for x in lines if x.startswith('ORIGIN')).split()[1:]))
        spacing=tuple(map(float,next(x for x in lines if x.startswith('SPACING')).split()[1:]))
        n=math.prod(dims); pos=f.tell()+n*12
        for name,count in FIELDS[1:]:
            f.seek(pos); tag=f.readline().decode('ascii').strip(); look=f.readline().decode('ascii').strip()
            assert tag==f'SCALARS {name} float {count}' and look=='LOOKUP_TABLE default',(name,tag,look)
            offsets[name]=f.tell();pos=f.tell()+n*4*count
        assert pos==path.stat().st_size,(pos,path.stat().st_size)
        return dims,origin,spacing,offsets

def sample(path,points, fine=False):
    dims,origin,spacing,offsets=header(path)
    assert dims==((1000,1000,540) if fine else (500,500,270))
    assert origin==(0.,0.,-20.) and spacing==((.5,)*3 if fine else (1.,)*3)
    assert len(points)==80 and set(int(p['id']) for p in points)==set(range(1,81))
    out=[]; dx=spacing[0]; label=2.25 if fine else 2.5; shift=(.5,.5) if fine else (1.,1.)
    with path.open('rb') as f:
        for p in points:
            xyz=(p['xls_xy'][0]+1010.50008-760+shift[0],p['xls_xy'][1]+1000.60004-750+shift[1],label)
            coords=[(a-b)/dx for a,b in zip(xyz,origin)]; idx=[math.floor(a) for a in coords]; w=[a-i for a,i in zip(coords,idx)]
            assert all(0<=i<n-1 for i,n in zip(idx,dims))
            sums={name:([0.,0.,0.] if count==3 else 0.) for name,count in FIELDS if name!='rho_avg'}
            solid=0.;corners=0
            for dz,dy,di in itertools.product((0,1),repeat=3):
                wt=(w[0] if di else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2]);k,j,i=idx[2]+dz,idx[1]+dy,idx[0]+di
                cell=(k*dims[1]+j)*dims[0]+i
                for name,count in FIELDS:
                    if name=='rho_avg':continue
                    f.seek(offsets[name]+cell*4*count)
                    vals=struct.unpack('>'+('f'*count),f.read(4*count))
                    assert all(math.isfinite(x) for x in vals),(p['id'],name)
                    if count==3:
                        for t,x in enumerate(vals):sums[name][t]+=wt*x
                    else:sums[name]+=wt*vals[0]
                    if name=='fluid':
                        fluid=vals[0]>.5;corners+=int(fluid);solid+=wt*(not fluid)
            assert sums['tke']>=-1e-5 and sums['speed2_mean']>=-1e-5
            out.append({'id':int(p['id']),'xyz_m':xyz,'k_m2s2':sums['tke'],'speed2_mean_m2s2':sums['speed2_mean'],'u_avg_mps':sums['u_avg'],'speed_mean_mps':sums['speed_mean'],'fluid_corners':corners,'solid_weight':solid})
    return {'source_vtk':str(path),'source_bytes':path.stat().st_size,'label_z_m':label,'wall_height_m':2.0,'dims':dims,'spacing':spacing,'rows':out}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vtk',default=SOURCE);ap.add_argument('--fine',action='store_true');ap.add_argument('--points',default='B2u_reference_points.json');ap.add_argument('--out',default='B2u_z2p5_80.json');args=ap.parse_args()
    p=pathlib.Path(args.vtk);assert p.is_file(),p
    points=json.loads(pathlib.Path(args.points).read_text())['rows']
    result=sample(p,points,args.fine); dest=pathlib.Path(args.out);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); sha=hashlib.sha256(dest.read_bytes()).hexdigest();dest.with_name(dest.name+'.sha256').write_text(f'{sha}  {dest.name}\n')
    print('SAMPLED',len(result['rows']),'VTK',result['source_vtk'],'OUTPUT',dest,'SHA256',sha,flush=True)
if __name__=='__main__':main()
