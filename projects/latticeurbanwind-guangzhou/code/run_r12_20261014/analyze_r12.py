"""R12 local independent sampling: fluid-normalized trilinear vs wall-normal shifts."""
from pathlib import Path
import json,csv,math,numpy as np
R=Path(__file__).parent;manifest=json.loads((R/'extract_manifest_r12.json').read_text());uref=manifest['uref']
# Reuse deduplicated STL section and exact-segment distance, not a direction inferred from errors.
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]);p=R.parent/'han2026_supp/LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl';arr=np.fromfile(p,dtype=D,offset=84);assert len(arr)==9210
segs={}
for t in arr['v'][:-12].astype(float):
 v=t.copy();v[:,0]-=760;v[:,1]-=750;hits=[]
 for i,j in ((0,1),(1,2),(2,0)):
  a,b=v[i],v[j]
  if (a[2]<=2<b[2]) or (b[2]<=2<a[2]):hits.append(a[:2]+(2-a[2])/(b[2]-a[2])*(b[:2]-a[:2]))
 if len(hits)==2 and np.linalg.norm(hits[0]-hits[1])>1e-5:
  key=tuple(sorted(tuple(np.round(q,4)) for q in hits));segs[key]=hits
seg=np.array(list(segs.values()));assert len(seg)==5540

def nearest_wall(q):
 a=seg[:,0];d=seg[:,1]-a;w=np.clip(np.einsum('ij,ij->i',q-a,d)/np.maximum(np.einsum('ij,ij->i',d,d),1e-20),0,1);feet=a+w[:,None]*d;idx=int(np.argmin(np.linalg.norm(feet-q,axis=1)));return feet[idx],float(np.linalg.norm(feet[idx]-q)),d[idx]

def sample(roi,x,y,z=2.,fluid_only=False):
 ax=[roi[t] for t in ('x','y','z')];ix=[int(np.searchsorted(a,v,side='right')-1) for a,v in zip(ax,(x,y,z))];ix=[min(max(i,0),len(a)-2) for i,a in zip(ix,ax)];assert all(a[i]<=v<=a[i+1] for a,i,v in zip(ax,ix,(x,y,z))),([x,y,z],[(a[0],a[-1],i) for a,i in zip(ax,ix)])
 w=[(v-a[i])/(a[i+1]-a[i]) for a,i,v in zip(ax,ix,(x,y,z))];uv=np.zeros(3);k=0.;sumw=0.;solidw=0.;nf=0
 for n in range(8):
  i,j,l=[ix[d]+((n>>d)&1) for d in range(3)];wt=np.prod([w[d] if n>>d&1 else 1-w[d] for d in range(3)]);isfluid=bool(roi['fluid'][l,j,i]);nf+=isfluid;solidw+=wt*(not isfluid)
  if isfluid or not fluid_only:uv+=wt*roi['u'][l,j,i];k+=wt*float(roi['k'][l,j,i]);sumw+=wt
 if sumw<1e-10:return None
 uv/=sumw;k/=sumw;s=float(np.linalg.norm(uv));return {'S':s/uref,'Sstar':math.sqrt(s*s+2*max(k,0))/uref,'k':k,'fluid_corners':nf,'solid_weight':round(float(solidw),6),'fluid_weight_used':round(float(sumw),6)}
rows=[]
for pid,meta in manifest['points'].items():
 roi=dict(np.load(R/meta['roi_file']));q=np.array(meta['sample_vtk_xy']);wall,dist,d=nearest_wall(q-np.array([1.,1.]));wall+=np.array([1.,1.]);normal=q-wall
 # If on the STL boundary, normal sign chosen by actual voxel fluid flag; not by observation error.
 if np.linalg.norm(normal)<1e-5:
  normal=np.array([-d[1],d[0]]);normal/=np.linalg.norm(normal)
  opts=[]
  for sign in (1,-1):
   probe=sample(roi,*(wall+sign*.75*normal),fluid_only=True)
   opts.append((probe['fluid_weight_used'] if probe else 0.,sign))
  normal*=max(opts)[1]
 else:normal/=np.linalg.norm(normal)
 # Controls already >5 m from the wall: test +1/+2 m displacement, not teleporting them to 1/2 m from a remote wall.
 methods={'original':q,'fluid_only':q,'wall_1m':(wall+normal if int(pid) in (50,51,52,54) else q+normal),'wall_2m':(wall+2*normal if int(pid) in (50,51,52,54) else q+2*normal),'wall_2m_fluid_only':(wall+2*normal if int(pid) in (50,51,52,54) else q+2*normal)}
 for name,xy in methods.items():
  val=sample(roi,*xy,fluid_only=(name in ('fluid_only','wall_2m_fluid_only')))
  assert val is not None,(pid,name,xy)
  rows.append({'id':int(pid),'role':'wall' if int(pid) in (50,51,52,54) else 'control','method':name,'stl_wall_distance_m':dist,'vtk_x':float(xy[0]),'vtk_y':float(xy[1]),'after':meta['after'],'before':meta['before'],'resid_after_S':val['S']-meta['after'],'resid_after_Sstar':val['Sstar']-meta['after'],**val})
out=R/'CaseE_wall_sampling_r12.csv'
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for pid in manifest['points']:
 print('POINT',pid,'STL dist',round(next(r['stl_wall_distance_m'] for r in rows if r['id']==int(pid)),3))
 for q in (x for x in rows if x['id']==int(pid)):print(q['method'],'S',round(q['S'],4),'S*',round(q['Sstar'],4),'obs',round(q['after'],4),'solid_weight',q['solid_weight'],'fluid_corners',q['fluid_corners'])
summary={}
for role in ('wall','control'):
 grp=[x for x in rows if x['role']==role];summary[role]={}
 for method in ('original','fluid_only','wall_1m','wall_2m','wall_2m_fluid_only'):
  s=[x for x in grp if x['method']==method];summary[role][method]={v:{'mae':float(np.mean([abs(x[v]-x['after']) for x in s])),'bias':float(np.mean([x[v]-x['after'] for x in s])),'mean_ratio':float(np.mean([x[v] for x in s])/np.mean([x['after'] for x in s]))} for v in ('S','Sstar')}
(R/'summary_r12.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
