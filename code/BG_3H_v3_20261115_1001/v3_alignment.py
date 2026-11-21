"""IoU-only horizontal registration and paired S1 sampling (stdlib, remote VM)."""
import csv, hashlib, json, math, pathlib, struct

def triangles(path):
    b=pathlib.Path(path).read_bytes(); n=struct.unpack_from('<I',b,80)[0]
    assert 84+50*n==len(b),(n,len(b))
    for t in struct.iter_unpack('<12fH',b[84:]):
        yield [tuple(t[i:i+3]) for i in (3,6,9)]

def footprint(stl,z):
    """Horizontal cut of closed STL: side triangles yield boundary segments."""
    segments=[]
    for tr in triangles(stl):
        pts=[]
        for a,b in ((0,1),(1,2),(2,0)):
            v,w=tr[a],tr[b]
            if (v[2]<z<w[2]) or (w[2]<z<v[2]):
                q=(z-v[2])/(w[2]-v[2]);pts.append((v[0]+q*(w[0]-v[0]),v[1]+q*(w[1]-v[1])))
        if len(pts)==2 and math.dist(pts[0],pts[1])>1e-6:segments.append(tuple(pts))
    return segments

def interval_rows(segments,origin,spacing,dims):
    # Half-open y crossings prevent vertices from being double counted.
    ys=[origin[1]+j*spacing[1] for j in range(dims[1])]
    for j,y in enumerate(ys):
        xs=[]
        for (x0,y0),(x1,y1) in segments:
            if (y0<=y<y1) or (y1<=y<y0):xs.append(x0+(y-y0)*(x1-x0)/(y1-y0))
        xs.sort()
        assert len(xs)%2==0,(y,len(xs),xs[:10])
        yield j,list(zip(xs[::2],xs[1::2]))

def labels(segments,o,sp,dims):
    out=set()
    for j,ranges in interval_rows(segments,o,sp,dims):
        for a,b in ranges:
            for i in range(max(0,math.floor((a-o[0])/sp[0])-1), min(dims[0],math.ceil((b-o[0])/sp[0])+2)):
                x=o[0]+i*sp[0]
                if a<x<b:out.add((i,j))
    return out

def components(cells):
    unseen=set(cells);groups=[]
    while unseen:
        seed=unseen.pop();stack=[seed];group={seed}
        while stack:
            x,y=stack.pop()
            for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if q in unseen:unseen.remove(q);group.add(q);stack.append(q)
        groups.append(group)
    return sorted(groups,key=lambda g:(min(x for x,y in g),min(y for x,y in g)))

def register(stl,read_vtk,vtk,evidence,case):
    f,m,dims,o,sp,mask,vel=read_vtk(vtk)
    try:
        assert sp==[2.,2.,2.]
        levels=([2.,10.,18.] if case!='BG_3H' else [2.,10.,18.,40.,58.]) if case!='CaseD' else [2.,10.,50.,98.]
        rows=[];total={offset:[0,0,0] for offset in ((0,0),(2,0),(0,2),(2,2))}
        level_data={}
        for height in levels:
            k=round((height-o[2])/sp[2]);assert abs(o[2]+k*sp[2]-height)<1e-8
            seg=footprint(stl,height);assert seg,(case,height)
            expected=labels(seg,o,sp,dims)
            # Ground footprint removed at these heights; score over union support only.
            observed={(i,j) for i,j in expected if not mask(i,j,k)}
            for dx,dy in total:
                sx,sy=int(dx/sp[0]),int(dy/sp[1]);shifted={(i+sx,j+sy) for i,j in expected if i+sx<dims[0] and j+sy<dims[1]}
                # Query all shifted candidates and base support; observation outside union is checked inside ROI.
                min_i=max(0,min(i for i,j in expected)-2);max_i=min(dims[0]-1,max(i for i,j in expected)+3)
                min_j=max(0,min(j for i,j in expected)-2);max_j=min(dims[1]-1,max(j for i,j in expected)+3)
                roi={(i,j) for i in range(min_i,max_i+1) for j in range(min_j,max_j+1) if not mask(i,j,k)}
                intersection=len(shifted&roi);union=len(shifted|roi)
                total[(dx,dy)][0]+=intersection;total[(dx,dy)][1]+=union;total[(dx,dy)][2]+=len(shifted)
                rows.append({'height_m':height,'offset_xy_m':[dx,dy],'intersection':intersection,'union':union,'iou':intersection/union if union else None,'predicted_cells':len(shifted),'native_solid_cells':len(roi)})
            level_data[height]=(expected,k)
        scores=[{'offset_xy_m':list(d),'intersection':v[0],'union':v[1],'iou':v[0]/v[1] if v[1] else None} for d,v in total.items()]
        # Ties prefer smaller shift, and uncertainty is preserved in the evidence.
        best=max(scores,key=lambda q:(q['iou'],-sum(q['offset_xy_m'])))
        assert best['iou']>0
        dx,dy=best['offset_xy_m'];sx,sy=int(dx/2),int(dy/2)
        per_building=[]
        if case.startswith('BG_'):
            groups=components(level_data[2.][0]);assert len(groups)==9,(case,len(groups))
            for ix,g in enumerate(groups,1):
                moved={(i+sx,j+sy) for i,j in g};cen=sorted(moved)[len(moved)//2]
                # Every footprint must be attached at 2m and retain its own top stratum.
                low=sum(not mask(i,j,round((18.-o[2])/2)) for i,j in moved)
                high=sum(not mask(i,j,round((58.-o[2])/2)) for i,j in moved) if case=='BG_3H' else 0
                above=sum(not mask(i,j,round(((62. if high else 22.)-o[2])/2)) for i,j in moved)
                base=sum(not mask(i,j,round((2.-o[2])/2)) for i,j in moved)
                assert base>0 and low>0 and above==0,(ix,base,low,high,above)
                per_building.append({'building':ix,'xy_extent_m':[o[0]+min(i for i,j in g)*2,o[0]+max(i for i,j in g)*2,o[1]+min(j for i,j in g)*2,o[1]+max(j for i,j in g)*2],'base_solid_cells':base,'roof_20m_cells':low,'roof_60m_cells':high,'above_roof_solid_cells':above})
            if case=='BG_3H':assert sum(q['roof_60m_cells']>0 for q in per_building)==1
            else:assert all(q['roof_60m_cells']==0 for q in per_building)
        report={'method':'closed STL horizontal cuts versus native fluid mask, discrete cell-centre occupancy; aggregate IoU selected before velocity extraction','case':case,'levels_m':levels,'candidates':rows,'aggregate':scores,'selected_offset_xy_m':[dx,dy],'per_building':per_building,'source_stl_sha256':hashlib.sha256(pathlib.Path(stl).read_bytes()).hexdigest()}
        (evidence/'iou_registration.json').write_text(json.dumps(report,indent=2))
        return dx,dy
    finally:m.close();f.close()

def sample_points(stl,read_vtk,vtk,evidence,source_csv,case,dx,dy,sha):
    f,m,dims,o,sp,mask,vel=read_vtk(vtk)
    try:
        wall=json.loads((evidence/'geometry_gate.json').read_text())['ground_wall_label_m']
        is_d=case=='CaseD';base=(850.,550.) if is_d else (dims[0],dims[1]);UH=6.65 if is_d else 3.1
        rows=[];zero=[]
        with open(source_csv,newline='',encoding='utf-8-sig') as inp:
            for rec in csv.DictReader(inp):
                x,y,h=(float(rec[key]) for key in ('x','y','z'))
                def one(ox,oy):
                    xyz=[x+base[0]+ox,y+base[1]+oy,max(wall+h,wall+sp[2]/2)]
                    lattice=[(v-a)/step for v,a,step in zip(xyz,o,sp)];ids=[math.floor(v) for v in lattice];fr=[v-i for v,i in zip(lattice,ids)]
                    assert all(0<=i<dim-1 for i,dim in zip(ids,dims)),(rec,ids)
                    comps=[0.,0.,0.];solids=[];weight_solid=0.
                    for n in range(8):
                        shift=[n>>d&1 for d in range(3)];weight=math.prod(fr[d] if shift[d] else 1-fr[d] for d in range(3))
                        if weight<=1e-12:continue
                        i,j,k=(ids[d]+shift[d] for d in range(3))
                        if not mask(i,j,k):solids.append([i,j,k]);weight_solid+=weight
                        for d,v in enumerate(vel(i,j,k)):comps[d]+=weight*v
                    assert all(map(math.isfinite,comps))
                    return {'luw_sample_xyz_m':xyz,'actual_agl_m':xyz[2]-wall,'u_mps':comps[0],'v_mps':comps[1],'w_mps':comps[2],'speed_over_UH':math.sqrt(sum(v*v for v in comps))/UH,'clamped':wall+h<xyz[2]-1e-9,'solid_corners':solids,'solid_weight':weight_solid}
                ident=rec['No'] if is_d else str(len(rows)+1)
                info={'kind':rec['kind'] if is_d else rec['plane'],'id':ident,'c38_xyz_m':[x,y,h]}
                if not is_d:info['zone']=rec['zone']
                rows.append({**info,**one(dx,dy)});zero.append({**info,**one(0,0)})
        assert len(rows)==(99 if is_d else 195 if case=='BG_1H' else 200)
        summary={'source_vtk':str(vtk),'source_vtk_size':pathlib.Path(vtk).stat().st_size,'source_vtk_sha256':sha(vtk),'origin_xyz_m':o,'spacing_xyz_m':sp,'wall_label_m':wall,'UH_mps':UH,'UH_height_m':100 if is_d else 20,'selected_offset_xy_m':[dx,dy],'rows':rows,'zero_offset_rows':zero,'clamped':sum(q['clamped'] for q in rows),'mixed':sum(q['solid_weight']>1e-12 for q in rows)}
        (evidence/'pointvalues.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
        return summary
    finally:m.close();f.close()
