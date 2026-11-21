"""Read-only bounded diagnostics from the completed Case D average VTK."""
import hashlib,json,math,pathlib,zipfile
import numpy as np

def extract(vtk, evidence, pointfile, gate, source_sha):
    vtk=pathlib.Path(vtk); evidence=pathlib.Path(evidence)
    h=hashlib.sha256()
    with vtk.open('rb') as f:
        header=[]
        while True:
            line=f.readline(); header.append(line.decode('ascii','replace').strip())
            if line.startswith(b'LOOKUP_TABLE'): break
        data_offset=f.tell()
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    # Hash the entire VTK, not just its payload.
    sha=hashlib.sha256()
    with vtk.open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):sha.update(block)
    dims=[int(x) for x in next(v for v in header if v.startswith('DIMENSIONS')).split()[1:]]
    origin=[float(x) for x in next(v for v in header if v.startswith('ORIGIN')).split()[1:]]
    spacing=[float(x) for x in next(v for v in header if v.startswith('SPACING')).split()[1:]]
    n=math.prod(dims); shape=(dims[2],dims[1],dims[0]); b=vtk.read_bytes()[:data_offset+64]
    assert header[-2]=='SCALARS u_avg float 3',header
    def field(name,base,count):
        marker=f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode()
        with vtk.open('rb') as f:
            f.seek(base); assert f.read(len(marker))==marker,name
        return np.memmap(vtk,mode='r',dtype='>f4',offset=base+len(marker),shape=shape+(() if count==1 else (count,)))
    velocity=np.memmap(vtk,mode='r',dtype='>f4',offset=data_offset,shape=shape+(3,))
    base=data_offset+n*3*4
    rho=field('rho_avg',base,1);base=rho.offset+n*4
    fluid=field('fluid',base,1);base=fluid.offset+n*4
    kfield=field('tke',base,1)
    assert kfield.offset+n*4==vtk.stat().st_size
    wall=float(gate['ground_wall_label_m']);assert spacing==[2.,2.,2.] and dims==[170,110,60]
    def sample(x,y,height):
        # Trilinear on the absolute label wall+height; solid corners reported separately.
        coords=[(x-origin[0])/2,(y-origin[1])/2,(wall+height-origin[2])/2]
        lo=[math.floor(v) for v in coords];fr=[v-a for v,a in zip(coords,lo)]
        assert all(0<=a<dim-1 for a,dim in zip(lo,dims)),(x,y,height,lo)
        accum=np.zeros(5,dtype=np.float64);solid_weight=0.
        for mask in range(8):
            shifts=[mask>>j&1 for j in range(3)]
            w=math.prod(fr[j] if shifts[j] else 1-fr[j] for j in range(3))
            if w<=1e-12:continue
            i,j,l=[lo[q]+shifts[q] for q in range(3)]
            if fluid[l,j,i]<=.5: solid_weight+=w
            accum[:3]+=w*velocity[l,j,i]
            accum[3]+=w*float(kfield[l,j,i]);accum[4]+=w*float(fluid[l,j,i])
        return {'u_mps':float(accum[0]),'v_mps':float(accum[1]),'w_mps':float(accum[2]),'k_solver':float(accum[3]),'speed_mps':float(np.linalg.norm(accum[:3])),'solid_weight':solid_weight}
    profile_heights=list(range(2,91,2))
    upstream=[{'x_m':x,'y_m':y,'height_agl_m':z,**sample(x,y,z)} for x in (2,10,50) for y in (10,110.0,210) for z in profile_heights]
    open_xy=[v['xy'] for v in gate['open_columns']]
    pts=json.loads(pathlib.Path(pointfile).read_text())['rows']
    streets={'sites':[(p['luw_sample_xyz_m'][0],p['luw_sample_xyz_m'][1],p['id']) for p in pts[:5]]}
    street_heights=list(range(2,31))
    neighborhood=[{'group':group,'id':ident,'x_m':x,'y_m':y,'height_agl_m':z,**sample(x,y,z)} for group,sites in [('open',[(x,y,str(i)) for i,(x,y) in enumerate(open_xy)]),*streets.items()] for x,y,ident in sites for z in street_heights]
    planes={}
    for height in (1,2,3,5,10):
        q=(wall+height-origin[2])/2; low=math.floor(q);frac=q-low
        a=np.asarray(velocity[low],dtype=np.float32); b=np.asarray(velocity[low+1],dtype=np.float32)
        v=a*(1-frac)+b*frac
        speed=np.sqrt(np.sum(v*v,axis=2,dtype=np.float32),dtype=np.float32)
        mask=np.asarray((fluid[low]>.5)&(fluid[low+1]>.5) if frac>0 else fluid[low]>.5,dtype=np.float32)
        speed[mask==0]=np.nan
        planes[f'speed_agl_{height}m_mps']=speed
        planes[f'fluid_agl_{height}m']=mask
    np.savez_compressed(evidence/'planes_1_2_3_5_10m.npz',**planes)
    expected={}
    inlet2=[v for v in upstream if v['x_m']==2 and v['y_m']==110.0 and v['height_agl_m']==2][0]['speed_mps']
    open2=[v['speed_mps'] for v in neighborhood if v['group']=='open' and v['height_agl_m']==2]
    ratios={}
    for g,sites in streets.items():
        ratios[g]=[]
        for _,_,ident in sites:
            at2=next(v for v in neighborhood if v['group']==g and v['id']==ident and v['height_agl_m']==2)
            at5=next(v for v in neighborhood if v['group']==g and v['id']==ident and v['height_agl_m']==5)
            ratios[g].append(None if at5['speed_mps']==0 or at2['solid_weight']>0 or at5['solid_weight']>0 else at2['speed_mps']/at5['speed_mps'])
    comparison={'inlet_x2_y110_agl2_speed_mps':inlet2,'AF_2m_speed_mps':None,'inlet_to_AF_ratio':None,'open_agl2_speeds_mps':open2,'open_mean_to_inlet_ratio':float(np.mean(open2)/inlet2) if inlet2 else None,'street_2m_to_5m_site_ratios':ratios,'street_ratio_means':{g:float(np.mean([x for x in v if x is not None])) if any(x is not None for x in v) else None for g,v in ratios.items()},'speed_definition':'magnitude of time-mean vector; null for zero denominator or solid support'}
    meta={'vtk_path':str(vtk),'vtk_size':vtk.stat().st_size,'vtk_sha256':sha.hexdigest(),'vtk_header':header,'dims_xyz':dims,'origin_xyz_m':origin,'spacing_xyz_m':spacing,'wall_label_m':wall,'point_source_sha256':source_sha,'profile_heights':'inclusive 2..90m by 2m; z=0..2m solid/unresolved at this 2m mesh','profile_def':'trilinear velocity, fluid positive-weight corners marked via solid_weight','planes_def':'trilinear speed from time-mean vector; NaN on solid; fluid mask all positive-weight corners fluid','comparison':comparison}
    for name,data in [('profiles_upstream.json',upstream),('profiles_open_streets.json',neighborhood),('vtk_header_sha256.json',meta)]: (evidence/name).write_text(json.dumps(data,indent=2,allow_nan=False))
    files=[evidence/name for name in ('profiles_upstream.json','profiles_open_streets.json','vtk_header_sha256.json','planes_1_2_3_5_10m.npz')]
    return {v.name:hashlib.sha256(v.read_bytes()).hexdigest() for v in files}
