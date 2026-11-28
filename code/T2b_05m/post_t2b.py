#!/usr/bin/env python3
"""Read-only VTK/STL registration and T2 point/plane postprocessing."""
import csv, hashlib, itertools, json, math, pathlib, struct, sys, time, traceback
import numpy as np

ROOT=pathlib.Path(__file__).resolve().parent
T2=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2b_05m')
T1=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u')
VTKS=[T2/'case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk',T1/'case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk']
STL=T2/'case_4gpu/proj_temp/CaseE_PF.stl'
class SmallField:
    def __init__(self,path,offset,dims,components): self.path=path;self.offset=offset;self.nx,self.ny,self.nz=dims;self.components=components
    def __getitem__(self,idx):
        k,j,i=idx;pos=self.offset+((k*self.ny+j)*self.nx+i)*4*self.components
        with self.path.open('rb') as f:f.seek(pos);return np.frombuffer(f.read(4*self.components),dtype='>f4').copy() if self.components==3 else struct.unpack('>f',f.read(4))[0]
    def tile(self,k,iy,ix):
        rows=[]
        with self.path.open('rb') as f:
            for j in iy:
                pos=self.offset+((k*self.ny+int(j))*self.nx+int(ix[0]))*4*self.components
                f.seek(pos);rows.append(np.frombuffer(f.read(len(ix)*4*self.components),dtype='>f4').reshape((len(ix),self.components)))
        return np.asarray(rows)

def vtk_open(path,small=False):
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
    raw=None if small else np.memmap(path,mode='r',dtype='u1')
    for name,components in [('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
        if name!='u_avg':
            with path.open('rb') as f:
                f.seek(pos)
                tag=f.readline().decode('ascii').strip();lookup=f.readline().decode('ascii').strip()
            assert tag==f'SCALARS {name} float {components}' and lookup=='LOOKUP_TABLE default',(name,tag,lookup)
            pos+=len((tag+'\n'+lookup+'\n').encode())
        shape=(nz,ny,nx,components) if components==3 else (nz,ny,nx)
        fields[name]=SmallField(path,pos,dims,components) if small else np.ndarray(shape=shape,dtype='>f4',buffer=raw,offset=pos)
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

def fit(v,tri,shifts,heights,ix_override=None,iy_override=None):
    nx,ny,nz=v['dims']; ox,oy,oz=v['origin'];dx=v['spacing'][0]
    ix=np.arange(max(1,math.ceil((35-ox)/dx)),min(nx-2,math.floor((465-ox)/dx))+1)
    iy=np.arange(max(1,math.ceil((35-oy)/dx)),min(ny-2,math.floor((465-oy)/dx))+1)
    if ix_override is not None: ix=np.asarray(ix_override)
    if iy_override is not None: iy=np.asarray(iy_override)
    xs=ox+ix*dx;ys=oy+iy*dx;out=[]
    for height in heights:
        k=round((height-oz)/dx);field=v['fields']['u_avg']; tile=field.tile(k,iy,ix) if isinstance(field,SmallField) else field[k,:,:,:][np.ix_(iy,ix)];actual=np.sum(np.asarray(tile)**2,axis=2)<1e-12
        for dz in shifts:
            seg=sections(tri,height-dz)
            for sx,sy in itertools.product(shifts,repeat=2):
                predicted=mask(xs-sx,ys-sy,seg)
                tp=int(np.count_nonzero(actual&predicted));na=int(actual.sum());npred=int(predicted.sum());union=na+npred-tp
                out.append({'z_vtk':height,'offset_xyz_m':[sx,sy,dz],'iou':tp/union if union else None,'tp':tp,'actual_zero':na,'predicted_solid':npred,'nsegments':len(seg)})
        print('FIT',v['path'],height,'zero=',na,'records=',len(out),flush=True)
        if ix_override is None:
            save_json('fit_'+('05' if dx==.5 else '1')+f'_z{height:g}.json',out[-len(shifts)**3:])
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

def save_json(name,obj):
    target=ROOT/name
    with target.open('x') as f: json.dump(obj,f,indent=2);f.write('\n')

def inlet_comparison(v2,v1):
    # Diagnostic only: same physical height and upstream station in the exported core.
    items=[]
    for h in (1.5,2.,5.,10.,15.9):
        pair=[]
        for v in (v2,v1):
            dx=v['spacing'][0]; ix=round((2.-v['origin'][0])/dx);iy=round((250.-v['origin'][1])/dx)
            kz=(h-v['origin'][2])/dx;k=math.floor(kz);w=kz-k
            assert 0<=ix<v['dims'][0] and 0<=iy<v['dims'][1] and 0<=k<v['dims'][2]-1
            f=v['fields']; u=np.asarray((1-w)*f['u_avg'][k,iy,ix]+w*f['u_avg'][k+1,iy,ix],dtype=float)
            tke=float((1-w)*f['tke'][k,iy,ix]+w*f['tke'][k+1,iy,ix])
            pair.append({'dx_m':dx,'sample_xyz_m':[v['origin'][0]+ix*dx,v['origin'][1]+iy*dx,h],
                         'u_avg_components_raw':u.tolist(),'u_avg_norm_raw':float(np.linalg.norm(u)),
                         'k_raw':tke})
        items.append({'height_m':h,'pair':pair,'U_norm_ratio_05_over_1':pair[0]['u_avg_norm_raw']/pair[1]['u_avg_norm_raw'] if pair[1]['u_avg_norm_raw'] else None,
                      'k_ratio_05_over_1':pair[0]['k_raw']/pair[1]['k_raw'] if pair[1]['k_raw'] else None})
    save_json('inlet_same_height.json',{'note':'VTK raw units; x=2 m, y=250 m; descriptive same-height comparison, not official inlet acceptance','items':items})
    print('INLET_DIAGNOSTIC_DONE',len(items),flush=True)

def select(fits,shifts,roof_heights):
    # Only heights with a building in all z-candidate slices qualify for z scoring.
    complete=[]
    for h in roof_heights:
        slab=[r for r in fits if r['z_vtk']==h]
        if all(any(r['offset_xyz_m'][2]==dz and r['predicted_solid']>0 and r['iou'] is not None for r in slab) for dz in shifts): complete.append(h)
    ground=[r for r in fits if r['z_vtk']==2. and r['offset_xyz_m'][2]==0. and r['iou'] is not None and r['predicted_solid']>0]
    assert ground, 'No building available for horizontal IoU registration'
    scores={xy:sum(r['iou'] for r in ground if r['offset_xyz_m'][:2]==list(xy)) for xy in itertools.product(shifts,repeat=2)}
    xy=max(scores,key=scores.get)
    byz={dz:sum(r['iou'] for r in fits if r['z_vtk'] in complete and r['offset_xyz_m']==[xy[0],xy[1],dz] and r['iou'] is not None) for dz in shifts}
    ranked=sorted(((value,-dz) for dz,value in byz.items()),reverse=True)
    margin=ranked[0][0]-ranked[1][0] if len(ranked)>1 and complete else None
    z=-ranked[0][1] if margin is not None and margin>1e-5 else None
    return {'horizontal_m':xy,'z_m':z,'roof_iou_sum_by_z':byz,'roof_heights_scored':complete,'roof_margin':margin,'horizontal_scores':{str(k):v for k,v in scores.items()},'z_status':'z 不可辨' if z is None else '可辨'}

def preflight():
    v=vtk_open(VTKS[0],small=True);tri,n=triangles(STL)
    print('STL triangles',n,'building_z_min_max',float(tri[:,:,2].min()),float(tri[:,:,2].max()))
    print('VTK header',v['dims'],v['origin'],v['spacing'],v['bytes'])
    assert v['dims']==(1000,1000,540)
    # Real-header VTK tile: small bounded reads near an actual building, no whole-field scan.
    seg=sections(tri,2.)
    mid=min(((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b in seg if 35<a[0]<465 and 35<a[1]<465)
    cx,cy=(round((mid[0]-v['origin'][0])/.5),round((mid[1]-v['origin'][1])/.5))
    fit_small=fit(v,tri,(0.,.5,1.),(2.,8.,17.,23.,26.,32.,59.),range(cx-30,cx+30),range(cy-30,cy+30))
    picked=select(fit_small,(0.,.5,1.),(8.,17.,23.,26.,32.,59.))
    print('tile records',len(fit_small),'small_tile_selection',picked)
    assert all(x['iou'] is None for x in fit_small if not x['actual_zero'] and not x['predicted_solid'])
    empty={'iou':None,'actual_zero':0,'predicted_solid':0}
    assert empty['iou'] is None and not empty['predicted_solid']
    no_roof=select([r for r in fit_small if r['z_vtk']==2.]+[dict(r,z_vtk=64.,iou=None,actual_zero=0,predicted_solid=0) for r in fit_small if r['z_vtk']==2.],(0.,.5,1.),(64.,))
    assert no_roof['z_m'] is None and no_roof['roof_heights_scored']==[]
    print('EMPTY_IOU_PASS',no_roof['z_status'])
    ref=json.loads((ROOT/'B2u_reference_points.json').read_text());old=json.loads((ROOT/'points_80_t2_old.json').read_text())
    with (ROOT/'widths.csv').open(newline='') as f: widths=list(csv.DictReader(f))
    with (ROOT/'baseline.csv').open(newline='') as f: baseline=list(csv.DictReader(f))
    rows=[]
    for p in ref['rows']:
        sample=point_sample(v,p,(1.,1.,0.));rows.append({'id':p['id'],'obs':p['after'],'Su_ratio':sample['Su']/ref['uref'],'fluid_corners':sample['fluid_corners'],'solid_weight':sample['solid_weight']})
    diff=max(abs(r['Su_ratio']-o['Su']) for r,o in zip(rows,old['rows']))
    tab=table(rows,baseline,widths)
    save_json('preflight_table_final.json',{'selection_tile':picked,'table':tab,'old_max_abs_diff':diff,'empty_iou':empty,'no_roof_selection':no_roof})
    assert diff<1e-9,diff
    print('PREFLIGHT_PASS 80 points / table / empty IoU / real STL and VTK tile; old_diff',diff)

def main():
    if '--preflight' in sys.argv: return preflight()
    assert ROOT.is_dir()
    v2,v1=map(vtk_open,VTKS)
    assert v2['dims']==(1000,1000,540) and v2['origin']==(0.,0.,-20.) and v2['spacing']==(.5,)*3
    assert v1['dims']==(500,500,270) and v1['spacing']==(1.,)*3
    tri,n=triangles(STL)
    roof_candidates=(8.,17.,23.,26.,32.,59.)
    fit2=fit(v2,tri,(0.,.5,1.),(2.,)+roof_candidates)
    fit1=fit(v1,tri,(0.,1.),(2.,)+roof_candidates)
    save_json('fit_05.json',fit2)
    save_json('fit_1.json',fit1)
    chosen=select(fit2,(0.,.5,1.),roof_candidates);chosen1=select(fit1,(0.,1.),roof_candidates)
    save_json('selection.json',{'chosen_05':chosen,'chosen_1':chosen1,'stl_building_z_range':[float(tri[:,:,2].min()),float(tri[:,:,2].max())]})
    ref=json.loads((ROOT/'B2u_reference_points.json').read_text());old_points=json.loads((ROOT/'points_80_t2_old.json').read_text());assert len(ref['rows'])==len(old_points['rows'])==80
    rows=[]
    for p in ref['rows']:
        samples={str((sx,sy,sz)):point_sample(v2,p,(sx,sy,sz)) for sx,sy,sz in itertools.product((0.,.5,1.),repeat=3)}
        old=samples[str((1.,1.,0.))];rows.append({'id':p['id'],'obs':p['after'],'xls_xy':p['xls_xy'],'samples':samples,'original':old})
    save_json('points_all_offsets.json',rows)
    old_by={p['id']:p for p in old_points['rows']}
    diffs=[abs(row['original']['Su']/ref['uref']-old_by[row['id']]['Su']) for row in rows]
    # Old T2 is a separate inlet configuration: retain differences, never require equality.
    with (ROOT/'widths.csv').open(newline='') as f:widths=list(csv.DictReader(f))
    with (ROOT/'baseline.csv').open(newline='') as f:baseline=list(csv.DictReader(f))
    def scored(shift):return [{'id':row['id'],'obs':row['obs'],'Su_ratio':row['samples'][str(shift)]['Su']/ref['uref'],'fluid_corners':row['samples'][str(shift)]['fluid_corners'],'solid_weight':row['samples'][str(shift)]['solid_weight']} for row in rows]
    chosen_shift=(.5,.5,0.)  # Frozen before T2b run; IoU remains a geometry diagnostic.
    result={'sources':[{k:v[k] for k in ('path','bytes','dims','origin','spacing')} for v in (v2,v1)],'stl':str(STL),'triangles_total':n,'triangles_used':len(tri),'stl_building_z_range':[float(tri[:,:,2].min()),float(tri[:,:,2].max())],'mask_method':'exact zero vector mean vs STL excluding final 12 base triangles; region x/y 35..465 m; half-open z sections','fit_05_path':str(ROOT/'fit_05.json'),'fit_1_path':str(ROOT/'fit_1.json'),'chosen_05':chosen,'chosen_1':chosen1,'chosen_shift_for_table':chosen_shift,'z_unresolved':chosen['z_m'] is None,'old_t2_plus1_max_abs_diff':max(diffs),'old_t2_plus1_diff_note':'expected to differ: corrected inlet mapping','comparison_table_plus1':table(scored((1.,1.,0.)),baseline,widths),'primary_table_plus05':table(scored(chosen_shift),baseline,widths),'planes':[],'native_flags_status':'native initialized flags exported separately at physical z=1.5/2m; verify flag slab and provenance, fluid scalar is not flags','stat_window':'62000 steps; last 40000 stride 80; expected 500 samples; verify against solver evidence separately','created_unix':time.time()}
    save_json('result.json',result)
    try: inlet_comparison(v2,v1)
    except Exception:
        (ROOT/'inlet_failure.txt').write_text(traceback.format_exc());print('INLET_DIAGNOSTIC_FAILED',flush=True)
    for plane in write_planes(v2):
        result['planes'].append(plane)
        # Save manifest after every completed plane, without overwriting existing results.
        with (ROOT/'planes.progress.jsonl').open('a') as f:f.write(json.dumps(plane)+'\n')
    save_json('result_complete.json',result)
    print('DONE',json.dumps({'old_t2_plus1_max_diff':max(diffs),'fixed_primary':chosen_shift,'iou_geometry_choice':chosen,'planes':len(result['planes']),'comparison_mae':result['comparison_table_plus1']['total']['MAE_05'],'primary_mae':result['primary_table_plus05']['total']['MAE_05']}),flush=True)
if __name__=='__main__':
    try: main()
    except BaseException:
        (ROOT/'failure_traceback.txt').write_text(traceback.format_exc());raise
