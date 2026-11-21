#!/usr/bin/env python3
"""Read-only VTK/STL registration and T2 point/plane postprocessing."""
import csv, hashlib, itertools, json, math, pathlib, struct, sys, time
import numpy as np

ROOT=pathlib.Path(__file__).resolve().parent
T2=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2_05m_full_retry2')
T1=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u')
VTKS=[T2/'case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk',T1/'case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk']
STL=T2/'case_4gpu/proj_temp/CaseE_PF.stl'
def vtk_open(path):
    with path.open('rb') as f:
        lines=[]
        for _ in range(25):
            line=f.readline().decode('ascii','strict').strip(); lines.append(line)
            if line.startswith('LOOKUP_TABLE'): break
        offset=f.tell()
    dims=tuple(map(int,next(x for x in lines if x.startswith('DIMENSIONS')).split()[1:]))
    origin=tuple(map(float,next(x for x in lines if x.startswith('ORIGIN')).split()[1:]))
    spacing=tuple(map(float,next(x for x in lines if x.startswith('SPACING')).split()[1:]))
    nx,ny,nz=dims; N=nx*ny*nz; pos=offset; fields={}
    # Map the file only once: independent memmaps remap all preceding bytes.
    raw=np.memmap(path,mode='r',dtype='u1')
    for name,components in [('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
        if name!='u_avg':
            with path.open('rb') as f:
                f.seek(pos)
                tag=f.readline().decode('ascii').strip();lookup=f.readline().decode('ascii').strip()
            assert tag==f'SCALARS {name} float {components}' and lookup=='LOOKUP_TABLE default',(name,tag,lookup)
            pos+=len((tag+'\n'+lookup+'\n').encode())
        shape=(nz,ny,nx,components) if components==3 else (nz,ny,nx)
        fields[name]=np.ndarray(shape=shape,dtype='>f4',buffer=raw,offset=pos)
        pos+=N*4*components
    assert pos==path.stat().st_size,(path,pos,path.stat().st_size)
    return {'path':str(path),'bytes':pos,'dims':dims,'origin':origin,'spacing':spacing,'fields':fields,'header':lines}

def triangles(path):
    with path.open('rb') as f:
        f.read(80); n=struct.unpack('<I',f.read(4))[0]
        data=np.fromfile(f,dtype=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('attr','<u2')]),count=n)
    assert len(data)==n and n==9210
    return data['v'][:-12].astype('f8'),n
# Match extract_B2u.py: half-open triangle z intersection, dedupe rounded segment endpoints.
def sections(tri,z):
    seg={}
    for t in tri:
        p=[]
        for a,b in ((0,1),(1,2),(2,0)):
            za,zb=t[a,2],t[b,2]
            if (za<=z<zb) or (zb<=z<za):
                q=(z-za)/(zb-za);p.append(tuple(t[a,:2]+q*(t[b,:2]-t[a,:2])))
        if len(p)==2 and math.dist(*p)>1e-5:
            key=tuple(sorted(tuple(round(float(c),4) for c in xy) for xy in p));seg[key]=p
    return list(seg.values())
def mask(xs,ys,seg):
    out=np.empty((len(ys),len(xs)),dtype=bool)
    for j,y in enumerate(ys):
        crossing=sorted(x0+(x1-x0)*(y-y0)/(y1-y0) for ((x0,y0),(x1,y1)) in seg if (y0<=y<y1) or (y1<=y<y0))
        assert len(crossing)%2==0,(y,len(crossing))
        out[j]=np.searchsorted(crossing,xs,side='left')%2==1
    return out

def point_sample(v,p,shift):
    dx=v['spacing'][0]; assert len(set(v['spacing']))==1
    xyz=(p['xls_xy'][0]+1010.50008-760+shift[0],p['xls_xy'][1]+1000.60004-750+shift[1],2.+shift[2])
    coord=[(a-b)/dx for a,b in zip(xyz,v['origin'])];idx=[math.floor(a) for a in coord];w=[a-i for a,i in zip(coord,idx)]
    assert all(0<=i<n-1 for i,n in zip(idx,v['dims'])),(xyz,idx)
    su=solid=0.;corners=0
    for dz,dy,di in itertools.product((0,1),repeat=3):
        weight=(w[0] if di else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2]); k,j,i=idx[2]+dz,idx[1]+dy,idx[0]+di
        su+=weight*float(v['fields']['speed_mean'][k,j,i]);fluid=float(v['fields']['fluid'][k,j,i])>.5
        corners+=int(fluid);solid+=weight*(not fluid)
    return {'Su':su,'fluid_corners':corners,'solid_weight':solid,'xyz_m':xyz}

def fit(v,tri,shifts,heights):
    nx,ny,nz=v['dims']; ox,oy,oz=v['origin'];dx=v['spacing'][0]
    ix=np.arange(max(1,math.ceil((35-ox)/dx)),min(nx-2,math.floor((465-ox)/dx))+1)
    iy=np.arange(max(1,math.ceil((35-oy)/dx)),min(ny-2,math.floor((465-oy)/dx))+1)
    xs=ox+ix*dx;ys=oy+iy*dx;out=[]
    for height in heights:
        k=round((height-oz)/dx);actual=np.sum(np.asarray(v['fields']['u_avg'][k,:,:,:][np.ix_(iy,ix)])**2,axis=2)<1e-12
        for dz in shifts:
            seg=sections(tri,height-dz)
            for sx,sy in itertools.product(shifts,repeat=2):
                predicted=mask(xs-sx,ys-sy,seg)
                tp=int(np.count_nonzero(actual&predicted));na=int(actual.sum());npred=int(predicted.sum());union=na+npred-tp
                out.append({'z_vtk':height,'offset_xyz_m':[sx,sy,dz],'iou':tp/union if union else None,'tp':tp,'actual_zero':na,'predicted_solid':npred,'nsegments':len(seg)})
        print('FIT',v['path'],height,flush=True)
    return out

def write_planes(v):
    outputs=[];nx,ny,nz=v['dims'];oz=v['origin'][2];dx=v['spacing'][2]
    for z in (1.5,2.):
        a=(z-oz)/dx;k=math.floor(a);w=a-k;assert 0<=k<nz-1
        for name in ('u_avg','speed_mean','tke','fluid'):
            dest=ROOT/f'plane_z{z:g}_{"Su" if name=="speed_mean" else "k" if name=="tke" else name}.f32le'
            arr=v['fields'][name];count=0;digest=hashlib.sha256()
            with dest.open('xb') as f:
                for j in range(ny):
                    line=np.asarray((1-w)*arr[k,j]+w*arr[k+1,j],dtype='<f4'); b=line.tobytes();f.write(b);digest.update(b);count+=len(b)
            outputs.append({'path':str(dest),'bytes':count,'sha256':digest.hexdigest(),'mtime':dest.stat().st_mtime,'z_m':z,'components':3 if name=='u_avg' else 1,'field':name,'lower_index':k,'upper_index':k+1})
    return outputs

def table(rows,old,geom):
    byid={int(r['id']):r for r in rows};base={int(r['id']):r for r in old};width={int(r['id']):r for r in geom}
    assert set(byid)==set(base)==set(width)==set(range(1,81))
    def vals(i):
        p=byid[i];o=float(base[i]['obs']); assert o>0 and abs(o-float(p['obs']))<1e-10
        a=float(base[i]['Su']);b=p['Su_ratio'];return o,a,b,a/o,b/o
    def group(ids):
        vs=[vals(i) for i in ids];n=len(vs)
        if not n:return {'N':0}
        return {'N':n,'MAE_1':sum(abs(a-o) for o,a,b,r1,r2 in vs)/n,'MAE_05':sum(abs(b-o) for o,a,b,r1,r2 in vs)/n,'ratio_total_1':sum(a for o,a,b,r1,r2 in vs)/sum(o for o,a,b,r1,r2 in vs),'ratio_total_05':sum(b for o,a,b,r1,r2 in vs)/sum(o for o,a,b,r1,r2 in vs),'delta_r':sum(r2-r1 for o,a,b,r1,r2 in vs)/n,'improved':sum(abs(b-o)<abs(a-o) for o,a,b,r1,r2 in vs),'worsened':sum(abs(b-o)>abs(a-o) for o,a,b,r1,r2 in vs),'ties':sum(abs(b-o)==abs(a-o) for o,a,b,r1,r2 in vs)}
    bins={'<4':[],'4-8':[],'8-15':[],'>=15':[],'width_missing':[]}
    for i in range(1,81):
        s=width[i]['width_min_m'];key='width_missing' if s=='' else '<4' if float(s)<4 else '4-8' if float(s)<8 else '8-15' if float(s)<15 else '>=15';bins[key].append(i)
    groups={key:group(ids) for key,ids in bins.items()};wide=groups['>=15']['delta_r']
    for key,g in groups.items():
        if g['N']:g['D']=g['delta_r']-wide
    near=[50,51,52,54,55,74]; near_rows=[]
    for i in near:
        o,a,b,r1,r2=vals(i);near_rows.append({'id':i,'obs':o,'Su_1':a,'Su_05':b,'r_1':r1,'r_05':r2,'delta_r':r2-r1,'improved':abs(b-o)<abs(a-o),'recovered':r2>r1 and abs(b-o)<abs(a-o),'wall_m':float(width[i]['wall_m']),'fluid_corners':byid[i]['fluid_corners'],'solid_weight':byid[i]['solid_weight']})
    total=group(list(range(1,81)));gnear=group(near)
    gates={'delta_mae_le_005':total['MAE_05']-total['MAE_1']<=.005,'narrow_n_is_4':groups['<4']['N']==4,'narrow_D_ge_010':groups['<4']['D']>=.10 if groups['<4']['N'] else None,'narrow_improved_ge_3_of_4':groups['<4']['improved']>=3 if groups['<4']['N']==4 else None,'wide_abs_delta_r_le_005':abs(wide)<=.05,'near_improved_ge_4_of_6':gnear['improved']>=4,'near_delta_r_excess_ge_010':gnear['delta_r']-wide>=.10}
    return {'total':total,'delta_mae':total['MAE_05']-total['MAE_1'],'groups':groups,'near_group':gnear,'near_points':near_rows,'gates':gates,'all_gates_pass':all(v is True for v in gates.values())}

def main():
    assert ROOT.is_dir()
    v2,v1=map(vtk_open,VTKS)
    assert v2['dims']==(1000,1000,540) and v2['origin']==(0.,0.,-20.) and v2['spacing']==(.5,)*3
    assert v1['dims']==(500,500,270) and v1['spacing']==(1.,)*3
    tri,n=triangles(STL)
    ref=json.loads((ROOT/'B2u_reference_points.json').read_text());old_points=json.loads((ROOT/'points_80_t2_old.json').read_text());assert len(ref['rows'])==len(old_points['rows'])==80
    fit2=fit(v2,tri,(0.,.5,1.),(2.,32.,64.));fit1=fit(v1,tri,(0.,1.),(2.,32.,64.))
    # Select x/y by aggregate IoU over heights; z only if roof height resolves it.
    def select(fits,shifts):
        roof=[x for x in fits if x['z_vtk']==64.]
        byz={s:max((x['iou'] for x in roof if x['offset_xyz_m'][2]==s and x['iou'] is not None),default=None) for s in shifts}
        scores={xy:sum(x['iou'] for x in fits if x['offset_xyz_m'][:2]==list(xy) and x['offset_xyz_m'][2]==0. and x['iou'] is not None) for xy in itertools.product(shifts,repeat=2)}
        xy=max(scores,key=scores.get)
        # tie or nearly indistinguishable (raster quantization): leave z unresolved.
        ranked=sorted(((v,k) for k,v in byz.items() if v is not None),reverse=True)
        z=ranked[0][1] if len(ranked)>1 and ranked[0][0]-ranked[1][0]>1e-5 else None
        return {'horizontal_m':xy,'z_m':z,'roof_iou_by_z':byz,'roof_margin':ranked[0][0]-ranked[1][0] if len(ranked)>1 else None,'horizontal_scores':{str(k):v for k,v in scores.items()}}
    chosen=select(fit2,(0.,.5,1.));chosen1=select(fit1,(0.,1.))
    rows=[]
    for p in ref['rows']:
        samples={str((sx,sy,sz)):point_sample(v2,p,(sx,sy,sz)) for sx,sy,sz in itertools.product((0.,.5,1.),repeat=3)}
        old=samples[str((1.,1.,0.))]; rows.append({'id':p['id'],'obs':p['after'],'xls_xy':p['xls_xy'],'samples':samples,'original':old})
    old_by={p['id']:p for p in old_points['rows']}
    diffs=[abs(row['original']['Su']/ref['uref']-old_by[row['id']]['Su']) for row in rows]
    assert max(diffs)<1e-9,max(diffs)
    with (ROOT/'widths.csv').open(newline='') as f:widths=list(csv.DictReader(f))
    with (ROOT/'baseline.csv').open(newline='') as f:baseline=list(csv.DictReader(f))
    def scored(shift):return [{'id':row['id'],'obs':row['obs'],'Su_ratio':row['samples'][str(shift)]['Su']/ref['uref'],'fluid_corners':row['samples'][str(shift)]['fluid_corners'],'solid_weight':row['samples'][str(shift)]['solid_weight']} for row in rows]
    chosen_shift=(chosen['horizontal_m'][0],chosen['horizontal_m'][1],chosen['z_m'] if chosen['z_m'] is not None else 0.)
    outputs=write_planes(v2)
    result={'sources':[{k:v[k] for k in ('path','bytes','dims','origin','spacing')} for v in (v2,v1)],'stl':str(STL),'triangles_total':n,'triangles_used':len(tri),'mask_method':'exact zero vector mean vs STL excluding final 12 base triangles; region x/y 35..465 m; half-open z sections','fit_05':fit2,'fit_1':fit1,'chosen_05':chosen,'chosen_1':chosen1,'chosen_shift_for_table':chosen_shift,'z_unresolved':chosen['z_m'] is None,'original_max_abs_diff':max(diffs),'original_table':table(scored((1.,1.,0.)),baseline,widths),'iou_table':table(scored(chosen_shift),baseline,widths),'planes':outputs,'native_flags_status':'not exported at physical z=1.5/2m; fluid scalar is not flags','stat_window':'62000 steps; last 40000 stride 80; expected 500 samples; verify against solver evidence separately','created_unix':time.time()}
    (ROOT/'points_all_offsets.json').write_text(json.dumps(rows,indent=2)+'\n')
    (ROOT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DONE',json.dumps({'old_max_diff':max(diffs),'chosen':chosen_shift,'planes':len(outputs),'original_mae':result['original_table']['total']['MAE_05'],'iou_mae':result['iou_table']['total']['MAE_05']}),flush=True)
if __name__=='__main__':main()
