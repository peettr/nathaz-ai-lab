#!/usr/bin/env python3
"""T14a archived-data analysis; T14b optional corner extraction result. Sources read-only."""
import csv, hashlib, json, math, struct, zipfile
from pathlib import Path
from collections import defaultdict
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
LAB=R.parent/'38_Collaborative_Research_Lab/06_Work/C38.2'
CASE=R/'06_Logs/C38.2_caseD_bg'
SOURCES={'CaseD':(CASE/'CaseD_v3_20261115_1001/caseD_result.zip',CASE/'CaseD_retry5_20261115_0242/stage/caseD/proj_temp/CaseD_PF.stl'), 'BG_1H':(CASE/'BG_1H_v4_20261115_1050/BG_1H_v4_result.zip',CASE/'BG_1H/stage/BG_1H/proj_temp/BG_1H_PF.stl'),'BG_3H':(CASE/'BG_3H_v4_20261115_1050/BG_3H_v4_result.zip',CASE/'BG_3H/stage/BG_3H/proj_temp/BG_3H_PF.stl')}
CASEA=R/'06_Logs/caseA_S1/s1_results.json'; DOBS=LAB/'data_caseD_derived/caseD_points.csv'; BOBS=LAB/'data_DiB2021_derived/bg_points.csv'
used={}
def blob(p):
 p=Path(p);b=p.read_bytes();used[str(p)]=hashlib.sha256(b).hexdigest();return b
def metrics(rows):
 p=[x[0] for x in rows];o=[x[1] for x in rows];assert len(p)>1 and all(math.isfinite(x) for x in p+o)
 a=sum(x*y for x,y in zip(p,o))/sum(x*x for x in p);m=sum((x-y)**2 for x,y in zip(p,o))/len(p);pat=sum((a*x-y)**2 for x,y in zip(p,o))/len(p)
 return {'n':len(p),'MSE':m,'a':a,'MSE_pat':pat,'phi':pat/m if m else None,'verdict':'格局主导' if m and pat/m>=2/3 else '水平主导' if m and pat/m<=1/3 else '中间'}
def stl_polys(path):
 b=blob(path);n=struct.unpack_from('<I',b,80)[0];assert len(b)==84+50*n
 seg=[];z=2.0
 for t in struct.iter_unpack('<12fH',b[84:]):
  v=[t[i:i+3] for i in (3,6,9)]; pts=[]
  for a,c in ((0,1),(1,2),(2,0)):
   q,w=v[a],v[c]
   if (q[2]<z<w[2]) or (w[2]<z<q[2]):
    f=(z-q[2])/(w[2]-q[2]);pts.append((q[0]+f*(w[0]-q[0]),q[1]+f*(w[1]-q[1])))
  if len(pts)==2 and math.dist(*pts)>1e-6:seg.append(pts)
 assert seg,(path,n)
 return seg
def coverage(seg,x,y):
 # 1 m cell-centre raster of the radius-50 m disk; half-open polygon crossings.
 hit=den=0
 for iy in range(math.floor(y-50),math.ceil(y+50)):
  cy=iy+.5; crossings=[]
  for (x0,y0),(x1,y1) in seg:
   if (y0<=cy<y1) or (y1<=cy<y0):crossings.append(x0+(cy-y0)*(x1-x0)/(y1-y0))
  crossings.sort();assert len(crossings)%2==0,(cy,len(crossings))
  for ix in range(math.floor(x-50),math.ceil(x+50)):
   cx=ix+.5
   if (cx-x)**2+(cy-y)**2>=2500:continue
   den+=1;hit+=int(any(a<=cx<b for a,b in zip(crossings[::2],crossings[1::2])))
 return hit/den

def main():
 drows=list(csv.DictReader(blob(DOBS).decode('utf-8-sig').splitlines()));brows=list(csv.DictReader(blob(BOBS).decode('utf-8-sig').splitlines()));a=json.loads(blob(CASEA));results={};geoms={};exclusions={}
 for name,(archive,stl) in SOURCES.items():
  with zipfile.ZipFile(archive) as z:
   assert z.testzip() is None; data=json.loads(z.read('pointvalues.json')); members=json.loads(z.read('sha256.json'));assert all(hashlib.sha256(z.read(k)).hexdigest()==h for k,h in members.items());used[str(archive)+'::pointvalues.json']=hashlib.sha256(z.read('pointvalues.json')).hexdigest()
  used[str(archive)]=hashlib.sha256(archive.read_bytes()).hexdigest(); rows=data['rows'];ref= drows if name=='CaseD' else [q for q in brows if q['cfg']==name[3:]]
  assert len(ref)==len(rows)
  groups=defaultdict(list);excluded=[];coords={}
  for i,(row,obs) in enumerate(zip(rows,ref)):
   assert all(abs(row['c38_xyz_m'][j]-float(obs[k]))<1e-8 for j,k in enumerate(('x','y','z'))),(name,i)
   group=row['kind'];assert group==(obs['kind'] if name=='CaseD' else obs['plane'])
   if row['clamped'] or row['solid_weight']>1e-12:
    excluded.append({'group':group,'id':row['id'],'clamped':row['clamped'],'solid_weight':row['solid_weight']});continue
   o=float(obs['Vs'])/data['UH_mps'] if name=='CaseD' else math.sqrt(sum(float(obs[c])**2 for c in 'UVW'))/data['UH_mps']
   groups[group].append((row['speed_over_UH'],o,row['luw_sample_xyz_m'],i))
  results[name]={group:metrics([(p,o) for p,o,_,_ in group_rows]) for group,group_rows in groups.items()}
  # Group rows retain source labels; additionally count distinct physical sites (not an extra independent group).
  exclusions[name]={'excluded':excluded,'labelled_n':len(rows),'unique_sites_n':len({tuple(q['c38_xyz_m']) for q in rows})}
  seg=stl_polys(stl);sites={tuple(q['luw_sample_xyz_m'][:2]):None for q in rows if not q['clamped'] and q['solid_weight']<=1e-12}
  for x,y in sites:sites[x,y]=coverage(seg,x-2,y-2) # align registered (+2,+2) sample with unshifted STL
  geoms[name]={'stl':str(stl),'method':'1 m cell-centre raster, horizontal STL cut z=2 m, disk centre de-registered (-2,-2) m; radius 50 m','cover_by_xy':{f'{x},{y}':v for (x,y),v in sites.items()}}
  for group,grows in groups.items():
   if len(grows)<2:continue
   cov=[sites[tuple(q[2][:2])] for q in grows];median=(sorted(cov)[(len(cov)-1)//2]+sorted(cov)[len(cov)//2])/2
   dense=[(p,o) for (p,o,_,_),c in zip(grows,cov) if c>=median];sparse=[(p,o) for (p,o,_,_),c in zip(grows,cov) if c<median]
   if dense and sparse:
    aa=results[name][group]['a'];ed=sum(aa*p-o for p,o in dense)/len(dense);es=sum(aa*p-o for p,o in sparse)/len(sparse);c=es-ed
    results[name][group]['contrast']={'median_cover':median,'n_dense':len(dense),'n_sparse':len(sparse),'mean_dense_e':ed,'mean_sparse_e':es,'C':c,'between_fraction':(c/2)**2/results[name][group]['MSE_pat']}
 for group,rows in a['grids']['dx2']['groups'].items():
  valid=[q for q in rows['rows'] if not q['clamped'] and not q['solid_corners']];results['CaseA_'+group]=metrics([(q['speed'],q['obs_speed']) for q in valid]);exclusions['CaseA_'+group]={'excluded_n':len(rows['rows'])-len(valid),'labelled_n':len(rows['rows'])}
 out={'design':str(R/'04_Decisions/R21.4a_T14_跨算例格局与采样模板_设计与判据_20261118.md'),'T14a':results,'geometry':geoms,'exclusions':exclusions,'T14b':{'status':'waiting for same-source B2u VTK 8-corner extraction; other seeds unavailable unless local fields found'},'input_sha256':used,'notes':['CaseD S/T and BG vertical/z0.1H are separately reported, not pooled as independent rows.','BG observations: magnitude of archived U,V,W divided by 3.1; CaseD Vs divided by 6.65.','C uses groupwise fitted a, dense median ties included. Raster is a documented finite-resolution approximation to geometric disk area; verify before treating as exact area.']}
 (O/'T14_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(O/'INPUT_SHA256.txt').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(used.items())))
 lines=['# T14 跨算例及近墙模板','', '指标按每个归档点组单独计算；不跨算例比较绝对值。','', '| 算例组 | n | MSE | a | MSE_pat | φ | 判词 | C | 组间占比 |','|---|---:|---:|---:|---:|---:|---|---:|---:|']
 for name,val in results.items():
  for group,m in (val.items() if name in SOURCES else [('',val)]):
   c=m.get('contrast',{});lines.append(f"| {name} {group} | {m['n']} | {m['MSE']:.6f} | {m['a']:.6f} | {m['MSE_pat']:.6f} | {m['phi']:.4f} | {m['verdict']} | {c.get('C',float('nan')):.6f} | {c.get('between_fraction',float('nan')):.4f} |")
 lines+=['','Case D/BG 的覆盖率用原 STL z=2 m 水平切片 + 1 m 中心采样圆盘；坐标撤销已登记 (+2,+2) m 偏移。Case D S/T 与 BG 两组各自配观测，同地点重复不当独立证据；详见 JSON。','T14b：待同源局部场角点提取后补全；本报告仅为 T14a 阶段。','输入及 member SHA256 见 INPUT_SHA256.txt。',''];(O/'RESULT_REPORT.md').write_text('\n'.join(lines));print('T14a',[(k,[(g,v['n'],round(v['phi'],4)) for g,v in q.items()] if k in SOURCES else (q['n'],round(q['phi'],4))) for k,q in results.items()])
if __name__=='__main__':main()
