"""Read-only C1/C05 native-mask and point comparison; offline, no solver."""
from pathlib import Path
import json, math, struct
import numpy as np
from scipy.ndimage import label, distance_transform_edt
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent; P=R.parent
coarse=P/'resolution_crop_v2'; fine=P/'resolution_c05'
A=json.loads((coarse/'C1v2_offset_samples.json').read_text()); B=json.loads((fine/'C05_offset_samples_a_r10.json').read_text())
assert len(A['rows'])==len(B['rows'])==55
ar={i['id']:i for i in A['rows']};br={i['id']:i for i in B['rows']};assert set(ar)==set(br)
# Native flags are x-fastest uint8, z=0..90 inclusive, TYPE_S bit 0.
flags1=np.memmap(coarse/'C1v2_flags_z0_90.bin',dtype='u1',mode='r',shape=(91,250,300))
flags05=np.memmap(fine/'C05_native_flags_z0_90.bin',dtype='u1',mode='r',shape=(91,500,600))
assert flags1.size==91*250*300 and flags05.size==91*500*600
porosity=[]
for z in (1,2,3,4,5):
    # Physical AGL z: floor lattice index z+20 or 2*z+40. Explicit common footprint only.
    s1=(flags1[20+z]&1)!=0;s05=(flags05[40+2*z]&1)!=0
    p1=1-float(s1.mean());p05=1-float(s05.mean())
    # Coarse cell center against four fine cells (not grid-independent geometry).
    fine4=s05.reshape(250,2,300,2).transpose(0,2,1,3)
    porosity.append(dict(z_m=z,solid_1m=int(s1.sum()),fluid_1m=int((~s1).sum()),porosity_1m=p1,solid_05m=int(s05.sum()),fluid_05m=int((~s05).sum()),porosity_05m=p05, coarse_solid_fine_any_fluid=int((s1 & (~fine4).any(axis=(2,3))).sum()),coarse_fluid_fine_any_solid=int(((~s1)&fine4.any(axis=(2,3))).sum())))
# z=2 masks for point-context; true means fluid.
f1=(flags1[22]&1)==0;f05=(flags05[44]&1)==0
# STL section at physical z=2, crop-stage STL uses physical world coordinates.
stl=coarse/'stage_C1v2/case/proj_temp/CaseE_PF.stl'
DT=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')])
with stl.open('rb') as fh:
    fh.read(80);n=struct.unpack('<I',fh.read(4))[0];faces=np.fromfile(fh,dtype=DT,count=n)['v']
assert len(faces)==n and n>12
tri=faces[:-12].astype(np.float64); z=2.0
az=tri[:,:,2];end=np.roll(tri,-1,axis=1)
hit=((az<=z)&(z<end[:,:,2]))|((end[:,:,2]<=z)&(z<az))
sel=hit.sum(axis=1)==2;t=tri[sel];e=end[sel];hh=hit[sel]
w=(z-t[:,:,2])/np.where(e[:,:,2]!=t[:,:,2],e[:,:,2]-t[:,:,2],1)
seg=(t+w[:,:,None]*(e-t))[:,:,:2][hh].reshape(-1,2,2)
# Remove exact duplicate section segments including opposite orientation.
key=np.round(np.sort(seg,axis=1)*10000).astype('i8').reshape(-1,4)
seg=seg[np.sort(np.unique(key,axis=0,return_index=True)[1])]
# Scan STL cross-sections along both axes at 1 m spacing. Interior gap = between consecutive two solid intervals.
gaps=[]
for axis in (0,1):
    other=1-axis
    for tline in np.arange((0 if axis==0 else 80)+.25,(300 if axis==0 else 330),1.):
        l=seg[:,0,axis];h=seg[:,1,axis]
        cross=((l<=tline)&(tline<h))|((h<=tline)&(tline<l))
        if not cross.any():continue
        pair=seg[cross];ll=pair[:,0,axis];hh=pair[:,1,axis]
        coord=pair[:,0,other]+(pair[:,1,other]-pair[:,0,other])*(tline-ll)/(hh-ll)
        vals=np.sort(coord)
        uniq=[float(vals[0])]
        for v in vals[1:]:
            if v-uniq[-1]>.002:uniq.append(float(v))
        if len(uniq)<4:continue
        # In a watertight section, successive crossing pairs enclose solid. Between pairs is a two-wall air gap.
        for i in range(1,len(uniq)-1,2):
            left,right=uniq[i:i+2];width=right-left
            if not (0<width<=10):continue
            xy=[0.,0.];xy[axis]=float(tline);xy[other]=(left+right)/2
            # Exact crossing counts alone do not prove a connected traversable street.
            if not (0<=xy[0]<300 and 80<=xy[1]<330):continue
            gaps.append(dict(axis='x_fixed' if axis==0 else 'y_fixed',transect=float(tline),width_m=float(width),center_xy=xy,edge_positions=[left,right]))
# sample segment distances (STL) via KDTree of <=0.1m samples: bounded approximation, not exact analytic minimum.
diff=seg[:,1]-seg[:,0];length=np.linalg.norm(diff,axis=1);ns=np.maximum(2,np.ceil(length/.1).astype(int)+1)
pts=np.concatenate([seg[i,0]+np.linspace(0,1,int(nn))[:,None]*diff[i] for i,nn in enumerate(ns)])
tree=cKDTree(pts)
# same physical XY for both outputs; sampling uses +one grid cell of solver registration.
rows=[]
for id in sorted(ar):
    ra=ar[id];rb=br[id]
    xy=np.array(ra['xls_xy'])+np.array([250.50008,250.60004])
    d_stl=float(tree.query(xy)[0]);g_near=min(gaps,key=lambda g: math.dist(xy,g['center_xy'])) if gaps else None
    def at(mask,dx):
        ix=int(np.clip(round(xy[0]/dx),0,mask.shape[1]-1));iy=int(np.clip(round((xy[1]-80)/dx),0,mask.shape[0]-1))
        # Local orientation-specific two-sided gap width in native fluid mask, at nearest center.
        def span(a,idx):
            if not a[idx]:return 0
            lo=idx;hi=idx
            while lo>0 and a[lo-1]:lo-=1
            while hi+1<len(a) and a[hi+1]:hi+=1
            if lo==0 or hi==len(a)-1:return None
            return hi-lo+1
        return dict(cell_xy=[ix,iy],fluid=bool(mask[iy,ix]),gap_x_cells=span(mask[iy],ix),gap_y_cells=span(mask[:,ix],iy))
    x=ra['sample']['plus_dx'];y=rb['sample']['plus_dx'];obs=float(ra['after']);s1=float(x['exp_ratio']);s05=float(y['exp_ratio'])
    rows.append(dict(id=id,xy=xy.tolist(),inlet_distance_m=float(xy[0]),wall_distance_sampled_stl_m=d_stl,wall_distance_cells_1m=d_stl,wall_distance_cells_05m=2*d_stl,nearest_stl_gap_width_m=(g_near['width_m'] if g_near else None),nearest_stl_gap_center_distance_m=(math.dist(xy,g_near['center_xy']) if g_near else None),C1_mask=at(f1,1),C05_mask=at(f05,.5),C1_Sstar=s1,C05_Sstar=s05,delta_Sstar=s05-s1,C1_abs_error=abs(s1-obs),C05_abs_error=abs(s05-obs),delta_abs_error=abs(s05-obs)-abs(s1-obs),C1_k=float(x['tke_m2s2']),C05_k=float(y['tke_m2s2'])))
# Cross-sections near walls can be blocked by pixelization even if STL gap exists. Quantify for gaps <=3m.
for g in gaps:
    xy=g['center_xy'];axis=0 if g['axis']=='x_fixed' else 1;other=1-axis
    def segment_status(mask,dx):
        fixed=int(np.clip(round((xy[axis]-(80 if axis==1 else 0))/dx),0,mask.shape[1-axis]-1))
        lo,hi=g['edge_positions']; start=max(0,int(math.ceil((lo-(80 if other==1 else 0))/dx)));stop=min(mask.shape[other==0 and 1 or 0],int(math.floor((hi-(80 if other==1 else 0))/dx))+1)
        # explicit axis mapping: x-fixed scans y (column), y-fixed scans x (row)
        arr=(mask[:,fixed] if axis==0 else mask[fixed,:]);stop=min(len(arr),stop)
        return int(arr[start:stop].sum())
    g['fluid_samples_1m']=segment_status(f1,1.);g['fluid_samples_05m']=segment_status(f05,.5)
narrow=[g for g in gaps if g['width_m']<=3]
# Cluster consecutive sampled cross-sections of the same orientation into corridor proxies.
# An x_fixed transect advances along x, y_fixed advances along y; orientations may double-count a junction.
def corridor_proxies(threshold):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    gg=[g for g in gaps if g['width_m']<=threshold]
    if not gg:return dict(components=0,one_meter_samples=0,longitudinal_proxy_length_m=0)
    centers=np.asarray([g['center_xy'] for g in gg]); pairs=cKDTree(centers).query_pairs(r=1.8)
    ii=[];jj=[]
    for a,b in pairs:
        if gg[a]['axis']!=gg[b]['axis']:continue
        if not .9<abs(gg[a]['transect']-gg[b]['transect'])<1.1:continue
        ii.extend((a,b));jj.extend((b,a))
    ncomp,lab=connected_components(coo_matrix((np.ones(len(ii),dtype='u1'),(ii,jj)),shape=(len(gg),len(gg))),directed=False)
    # number of 1m-spaced transects is a length proxy, not a traced unique street centerline.
    return dict(components=int(ncomp),one_meter_samples=len(gg),longitudinal_proxy_length_m=float(len(gg)),components_ge_3_samples=int(sum(np.sum(lab==k)>=3 for k in range(ncomp))))
# Grid-only cross-section count at z=2: interior fluid runs bounded by solid at both ends, sampled per row/col.
def grid_cross(mask,dx):
    counts={2:0,3:0}; summed={2:0.,3:0.}; rec=[]
    for axis in (0,1):
        for j in range(mask.shape[axis]):
            line=mask[j,:] if axis==0 else mask[:,j]
            starts=np.flatnonzero(line & ~np.r_[False,line[:-1]])
            ends=np.flatnonzero(line & ~np.r_[line[1:],False])
            for lo,hi in zip(starts,ends):
                if lo==0 or hi==len(line)-1:continue
                width=int(hi-lo+1)
                if width>3:continue
                xy=[(lo+hi)/2*dx,j*dx+80] if axis==0 else [j*dx,(lo+hi)/2*dx+80]
                rec.append((width,xy))
                for threshold in (2,3):
                    if width<=threshold:counts[threshold]+=1;summed[threshold]+=width*dx
    return dict(transect_counts=counts,summed_open_width_m=summed,not_unique_street_lengths=True)
# Threshold by physical 1 m / 2 m / 3 m, with both grids. Grid counts above represent *cells*, not meters.
groups={}
for name,sel in [('wall_under_1m',lambda r:r['wall_distance_sampled_stl_m']<1),('wall_1to3m',lambda r:1<=r['wall_distance_sampled_stl_m']<3),('wall_3plus_m',lambda r:r['wall_distance_sampled_stl_m']>=3),('near_inlet_x_le_100',lambda r:r['inlet_distance_m']<=100),('mid_x_100to200',lambda r:100<r['inlet_distance_m']<=200),('far_x_gt200',lambda r:r['inlet_distance_m']>200),('local_gap_le_3m',lambda r:r['nearest_stl_gap_width_m']<=3 and r['nearest_stl_gap_center_distance_m']<=3),('other',lambda r:not(r['nearest_stl_gap_width_m']<=3 and r['nearest_stl_gap_center_distance_m']<=3))]:
    v=[r for r in rows if sel(r)]
    groups[name]=dict(n=len(v),mean_delta_Sstar=(float(np.mean([r['delta_Sstar'] for r in v])) if v else None),mean_delta_abs_error=(float(np.mean([r['delta_abs_error'] for r in v])) if v else None),improved=sum(r['delta_abs_error']<0 for r in v),worsened=sum(r['delta_abs_error']>0 for r in v),ids=[r['id'] for r in v])
# zero masks: fluid connected region from nearest x=5 inlet interior in z=2 plane, 4-neighbor flood.
conn={}
for name,mask,dx in [('C1',f1,1.),('C05',f05,.5)]:
    labels,num=label(mask,np.array([[0,1,0],[1,1,1],[0,1,0]],dtype='u1'))
    xcol=int(5/dx);lab,ct=np.unique(labels[:,xcol][labels[:,xcol]>0],return_counts=True)
    # identify dominant inlet-accessible connected region
    dom=int(lab[np.argmax(ct)]) if len(lab) else 0
    conn[name]=dict(components=int(num),main_inlet_component_size=int((labels==dom).sum()),points={str(r['id']):int(labels[r[name+'_mask']['cell_xy'][1],r[name+'_mask']['cell_xy'][0]])==dom for r in rows if r['id'] in (50,51,52,54,23,25,37,17)})
out=dict(method='z=1..5 AGL mapped to native z=20+z and 40+2z; STL z=2 cross sections; paired 55 points; horizontal/vertical sections are counts of transects, NOT unique street counts or lengths',porosity=porosity,stl_segments=int(len(seg)),stl_gaps_total=len(gaps),stl_gaps_le_2m=sum(g['width_m']<=2 for g in gaps),stl_gaps_le_3m=len(narrow),corridor_2m=corridor_proxies(2),corridor_3m=corridor_proxies(3),stl_gap_width_quantiles_m={str(q):float(np.quantile([g['width_m'] for g in gaps],q)) for q in (.1,.25,.5,.75,.9)},stl_gaps_le_3m_1m_blocked_05m_open=sum(g['fluid_samples_1m']==0 and g['fluid_samples_05m']>0 for g in narrow),stl_gaps_le_3m_1m_one_or_two_05m_more=sum(0<g['fluid_samples_1m']<=2 and g['fluid_samples_05m']>2 for g in narrow),narrow_gaps=[g for g in narrow],grid_runs_C1=grid_cross(f1,1),grid_runs_C05=grid_cross(f05,.5),connectivity=conn,points=rows,groups=groups)
(R/'analysis.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
import csv
with (R/'points_55.csv').open('w',newline='') as fh:
    fields=('id','xy','wall_distance_sampled_stl_m','nearest_stl_gap_width_m','nearest_stl_gap_center_distance_m','C1_mask','C05_mask','C1_Sstar','C05_Sstar','delta_Sstar','C1_abs_error','C05_abs_error','delta_abs_error','C1_k','C05_k')
    writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in rows)
with (R/'narrow_gap_transects.csv').open('w',newline='') as fh:
    fields=('axis','transect','width_m','center_xy','edge_positions','fluid_samples_1m','fluid_samples_05m')
    writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in narrow)
print(json.dumps({k:out[k] for k in ('porosity','stl_segments','stl_gaps_total','stl_gaps_le_2m','stl_gaps_le_3m','stl_gap_width_quantiles_m','stl_gaps_le_3m_1m_blocked_05m_open','stl_gaps_le_3m_1m_one_or_two_05m_more','grid_runs_C1','grid_runs_C05','connectivity','groups')},indent=2))
print('PROTECTED',[(r['id'],round(r['wall_distance_sampled_stl_m'],2),round(r['nearest_stl_gap_width_m'],2),round(r['nearest_stl_gap_center_distance_m'],2),round(r['delta_Sstar'],3),round(r['delta_abs_error'],3)) for r in rows if r['id'] in (50,51,52,54,23,25,37,17)])
