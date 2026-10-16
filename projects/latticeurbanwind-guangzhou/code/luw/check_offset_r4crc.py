"""Read-only evidence: STL footprint vs zero-speed VTK cells; sample both coordinate hypotheses.
Run on CRC after successful LUW job. Keep VTK on CRC; write only small JSON.
"""
from pathlib import Path
import json, math, mmap, struct, sys, itertools

root=Path(sys.argv[1]); assert (root/'exit.code').read_text().strip()=='0'
files=list((root/'case_west/RESULTS/vtk').glob('*_avg*.vtk')); assert len(files)==1, files
vtk=files[0]; stl=root/'case_west/proj_temp/CaseE_PF.stl'
with vtk.open('rb') as f:
    header=[]
    for _ in range(25):
        line=f.readline().decode('ascii','replace').strip(); header.append(line)
        if line.startswith('LOOKUP_TABLE'): break
    offset=f.tell()
assert header[-2].startswith('SCALARS u_avg') and header[-1].startswith('LOOKUP_TABLE'), header
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:])
org=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:])); dx=float(next(x for x in header if x.startswith('SPACING')).split()[1]); assert .7<dx<2.0
with stl.open('rb') as f:
    f.read(80); count=struct.unpack('<I',f.read(4))[0]
    tris=[]
    for _ in range(count):
        rec=f.read(50); tris.append(struct.unpack_from('<9f',rec,12))
assert count==9210, count
# Ignore 12 triangles of the outer base. The no-building domain is not our mask target.
tris=tris[:-12]
points=json.loads((root/'points_w_r4crc.json').read_text()); assert len(points['rows'])==80

# Intersect each triangle with z-plane; horizontal triangles do not contribute to
# odd/even x-ray interior test. Vertical face pairs have a common crossing, so
# keep each physical face segment once (round coordinates to mitigate float noise).
def sections(z):
    segs={}
    for t in tris:
        v=[t[i:i+3] for i in (0,3,6)]; p=[]
        for a,b in ((0,1),(1,2),(2,0)):
            za,zb=v[a][2],v[b][2]
            if (za<=z<zb) or (zb<=z<za):
                q=(z-za)/(zb-za);p.append((v[a][0]+q*(v[b][0]-v[a][0]),v[a][1]+q*(v[b][1]-v[a][1])))
        if len(p)==2 and math.dist(*p)>1e-5:
            k=tuple(sorted(tuple(round(c,4) for c in v) for v in p));segs[k]=p
    return list(segs.values())

def mask(ys,xs,z):
    seg=sections(z); bits=[]
    for y in ys:
        crossings=[]
        for (x0,y0),(x1,y1) in seg:
            if (y0<=y<y1) or (y1<=y<y0):
                crossings.append(x0+(x1-x0)*(y-y0)/(y1-y0))
        crossings.sort(); assert len(crossings)%2==0,(z,y,len(crossings))
        row=[]; parity=0;j=0
        for x in xs:
            while j<len(crossings) and crossings[j]<x: parity^=1;j+=1
            row.append(bool(parity))
        bits.extend(row)
    return bits,len(seg)

def interp(m,x,y,z):
    frac=[(val-start)/dx for val,start in zip((x,y,z),org)]; ids=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,ids)]
    vec=[0.,0.,0.];nfluid=0
    for c in range(8):
        i=ids[0]+(c&1);j=ids[1]+((c>>1)&1);k=ids[2]+((c>>2)&1)
        assert 0<=i<nx and 0<=j<ny and 0<=k<nz,(i,j,k)
        v=struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
        nfluid+=int(sum(a*a for a in v)>1e-12)
        weight=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3))
        for d in range(3):vec[d]+=weight*v[d]
    return math.sqrt(sum(v*v for v in vec)),nfluid

with vtk.open('rb') as f:
    m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
    # Build a full region mask once per height, sample its inner region to avoid
    # base/exterior and exact-shape coincidences due to grid rounding.
    ix=range(max(1,math.ceil((506-org[0])/dx)),min(nx-2,math.floor((916-org[0])/dx))+1)
    iy=range(max(1,math.ceil((145-org[1])/dx)),min(ny-2,math.floor((551-org[1])/dx))+1)
    xs=[org[0]+i*dx for i in ix];ys=[org[1]+j*dx for j in iy]
    fit=[]
    for ztarget in (2.,10.,20.):
        k=round((ztarget-org[2])/dx);z=org[2]+k*dx
        actual=[]
        for j in iy:
            for i in ix:
                v=struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
                actual.append(sum(a*a for a in v)<1e-12)
        for ox,oy,oz in itertools.product((0.,dx),repeat=3):
            predicted,nseg=mask([y-oy for y in ys],[x-ox for x in xs],z-oz)
            tp=sum(a and b for a,b in zip(actual,predicted));nsolid=sum(actual);npred=sum(predicted)
            fit.append({'z_vtk':z,'offset_xyz':[ox,oy,oz],'tp':tp,'actual_zero':nsolid,'predicted_solid':npred,'iou':tp/(nsolid+npred-tp) if nsolid+npred-tp else None,'precision':tp/nsolid if nsolid else None,'recall':tp/npred if npred else None,'nsegments':nseg})
    # For a coordinate offset of +dx, physical STL point is at VTK position +dx.
    rows=[]
    for p in points['rows']:
        old=list(p['local_xy'])+[2.]
        sample={}
        for label,shift in (('no_offset',(0.,0.,0.)),('plus_dx',(dx,dx,dx))):
            u,nfluid=interp(m,*[v+s for v,s in zip(old,shift)])
            sample[label]={'sim_ratio':u/points['uref'],'fluid_corners':nfluid}
        rows.append({'id':p['id'],'xls_xy':p['xls_xy'],'before':p['before'],'after':p['after'],'sample':sample})
    m.close()
out={'vtk':str(vtk),'origin':org,'dx':dx,'quantity':'magnitude of vector-interpolated mean u at STL z=2m / profile.dat U(15.9m)','mask_note':'STL cross-section at VTK z minus proposed offset; zero-speed exact threshold 1e-6 m/s; base triangles excluded','mask_fit':fit,'rows':rows}
(root/'offset_samples_r4crc.json').write_text(json.dumps(out,indent=2));print('WROTE offset_samples_r4crc.json',len(rows),'points',len(fit),'fits')
for z in sorted(set(q['z_vtk'] for q in fit)):
    print('z',z,sorted((q for q in fit if q['z_vtk']==z),key=lambda q:q['iou'] or -1,reverse=True)[:4])
