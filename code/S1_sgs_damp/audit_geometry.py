"""Read-only geometry audit: compare native TYPE_S and original STL polygon parity."""
from pathlib import Path
import numpy as np, json,struct,csv
R=Path(__file__).resolve().parent
base=Path('./24_Urban_Wind_LBM/06_Logs')
flags=np.load(base/'wp1b_ibm/phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']
f=open(base/'wp1b_ibm/inflow_ti/stage_B/case/proj_temp/CaseE_PF.stl','rb');f.read(80);n=struct.unpack('<I',f.read(4))[0];tri=np.fromfile(f,dtype=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')]),count=n)['v'][:-12].astype('f8');f.close()
points=json.loads((base/'wp1b_ibm/inflow_ti/B2_offset_samples.json').read_text())['rows']

def mask(stl_z,shift_xy):
 a=tri; b=np.roll(a,-1,axis=1)
 hit=((a[:,:,2]<=stl_z)&(stl_z<b[:,:,2]))|((b[:,:,2]<=stl_z)&(stl_z<a[:,:,2]))
 keep=hit.sum(axis=1)==2
 aa=a[keep];bb=b[keep];hh=hit[keep];tt=(stl_z-aa[:,:,2])/np.where(bb[:,:,2]!=aa[:,:,2],bb[:,:,2]-aa[:,:,2],1.)
 seg=(aa+tt[:,:,None]*(bb-aa))[:,:,:2][hh].reshape(-1,2,2)
 out=np.zeros((500,500),dtype=bool)
 for yi in range(500):
  y=yi-shift_xy;lo=seg[:,0,1];hi=seg[:,1,1];select=((lo<=y)&(y<hi))|((hi<=y)&(y<lo));s=seg[select];
  if not len(s):continue
  crosses=np.sort(s[:,0,0]+(y-s[:,0,1])*(s[:,1,0]-s[:,0,0])/(s[:,1,1]-s[:,0,1]));
  if len(crosses)%2:continue
  xx=np.arange(500)-shift_xy
  out[yi]=np.searchsorted(crosses,xx,side='left')%2==1
 return out
solid=(flags[22]&1)!=0
fits=[]
for z in (1.,2.,3.):
 for shift in (0.,1.,2.):
  predicted=mask(z,shift);overlap=np.count_nonzero(solid&predicted);union=np.count_nonzero(solid|predicted)
  fits.append(dict(stl_z=z,shift_xy=shift,iou=overlap/union,extra_native=int(np.count_nonzero(solid&~predicted)),miss_native=int(np.count_nonzero(predicted&~solid))))
best=max(fits,key=lambda r:r['iou']);pred=mask(best['stl_z'],best['shift_xy']);extra=solid&~pred;miss=pred&~solid
# Also use the solver-transformed STL with physical z of the same AGL slice, avoiding proxy-to-proxy claims.
rows=[]
for p in points:
 x,y=np.asarray(p['xls_xy'])+np.asarray([250.50008,250.60004]);ix=round(x);iy=round(y)
 x0=max(0,ix-10);x1=min(500,ix+11);y0=max(0,iy-10);y1=min(500,iy+11)
 sl=(slice(y0,y1),slice(x0,x1));sim=p['sample']['plus_dx']['sim_ratio']/p['after']
 rows.append(dict(id=p['id'],x=float(x),y=float(y),S_over_W=float(sim),class_B2='fast' if sim>1.2 else ('slow' if sim<.8 else 'middle'),native_solid=int(solid[sl].sum()),stl_solid=int(pred[sl].sum()),native_only=int(extra[sl].sum()),stl_only=int(miss[sl].sum()),total=int(solid[sl].size)))
with (R/'geometry_points.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
summary={'fits':fits,'chosen':best,'slice_z_native':22,'global':{'native_solid':int(solid.sum()),'stl_solid':int(pred.sum()),'native_only':int(extra.sum()),'stl_only':int(miss.sum())},'groups':{}}
for c in ('fast','slow','middle'):
 v=[r for r in rows if r['class_B2']==c];summary['groups'][c]={'n':len(v),'native_only_total':sum(r['native_only'] for r in v),'stl_only_total':sum(r['stl_only'] for r in v),'native_only_median':float(np.median([r['native_only'] for r in v])),'stl_only_median':float(np.median([r['stl_only'] for r in v]))}
summary['native_only_coords_xyz_at_z22']=[[int(x),int(y),22] for y,x in np.argwhere(extra)]
summary['height_checks']=[]
for zi in (22,25,30,40,60,80):
 # For a solver index zi, stage STL is sampled in the original z coordinate zi-21.
 native=(flags[zi]&1)!=0
 proxy=mask(float(zi-21),1.)
 summary['height_checks'].append(dict(solver_z=zi,native_solid=int(native.sum()),proxy_solid=int(proxy.sum()),native_only=int(np.count_nonzero(native&~proxy)),stl_only=int(np.count_nonzero(proxy&~native)),iou=float(np.count_nonzero(native&proxy)/max(1,np.count_nonzero(native|proxy)))))
(R/'geometry_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
