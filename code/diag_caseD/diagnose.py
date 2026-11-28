#!/usr/bin/env python3
"""Read-only Case D diagnostic; no solver, remote session, or input mutation."""
import csv, json, zipfile, hashlib, math, struct, statistics
from pathlib import Path
from PIL import Image,ImageDraw
import xlrd
P=Path('./24_Urban_Wind_LBM')
R=Path('./38_Collaborative_Research_Lab/06_Work/C38.2')
O=Path(__file__).parent; D=P/'06_Logs/C38.2_caseD_bg'; Z=D/'CaseD_retry6_20261115_0411/caseD_result.zip'; A=R/'data_AIJ_CaseD_zenodo15402669'; F=R/'data_caseD_derived/caseD_points.csv'; B=D/'CaseD_retry5_20261115_0242/stage/caseD/proj_temp/CaseD_PF.stl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(Z) as z:
 assert z.testzip() is None
 hashes=json.loads(z.read('sha256.json'))
 assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
 data=json.loads(z.read('pointvalues.json')); gate=json.loads(z.read('geometry_gate.json'))
 rows=data['rows']; log=z.read('solver.log').decode(errors='replace')
assert len(rows)==99 and gate['dims']==[850,550,300]
points=list(csv.DictReader(F.open(encoding='utf-8-sig',newline='')))
assert len(points)==99
key=lambda r:(r['kind'],str(int(r.get('id',r.get('No')))))
meas={key(r):r for r in points}; sim={key(r):r for r in rows}; assert sim.keys()==meas.keys()
# Full-scale geometry from frozen binary deck: project upward-facing roof facets.
raw=B.read_bytes(); assert len(raw)>=84; n=struct.unpack_from('<I',raw,80)[0];assert len(raw)==84+50*n
tri=[]
for k in range(n):
 q=struct.unpack_from('<12fH',raw,84+k*50); v=[(q[3+i*3],q[4+i*3],q[5+i*3]) for i in range(3)]
 if max(a[2] for a in v)-min(a[2] for a in v)<.001 and 9.5<=v[0][2]<=100.5 :tri.append(v)
assert tri
w,h=1600,1000; im=Image.new('RGB',(w,h),'white'); dr=ImageDraw.Draw(im)
# Panel 1: full domain; panel 2: focus around benchmark geometry.
def pt(x,y,zoom=False):
 if zoom:return (round(800+(x-850)*2.2),round(520-(y-550)*2.2))
 return (round(35+x*.42),round(930-y*.42))
for zoom in (False,True):
 for v in tri:
  col='#f3b277' if v[0][2]<20 else '#8542a0'
  dr.polygon([pt(x,y,zoom) for x,y,_ in v],fill=col)
 for r in rows:
  x,y,_=r['luw_sample_xyz_m'];px,py=pt(x,y,zoom);col='#0e64c8' if r['kind']=='S' else '#147a42';rad=4 if zoom else 3
  dr.ellipse((px-rad,py-rad,px+rad,py+rad),fill=col)
 for q in gate['open_columns']:
  px,py=pt(*q['xy'],zoom);dr.line((px-7,py,px+7,py),fill='red',width=2);dr.line((px,py-7,px,py+7),fill='red',width=2)
dr.text((25,15),'Full domain 1700x1100m; mapped roofs & 99 measurement sites',fill='black')
dr.text((25,480),'Zoom: x=850,y=550 center; blue S, green T, red + gate columns',fill='black')
dr.text((25,955),'Native fluid mask is NOT archived; red + are four confirmed open-ground columns only.',fill='black')
if not (O/'points_roofs_gate_columns.png').exists():
 im.save(O/'points_roofs_gate_columns.png')
# Unit and coordinate readback of raw CSV and workbook.
book=xlrd.open_workbook(str(A/'LF_caseD.xls')); ss=book.sheet_by_name('Results (Exp_S)'); st=book.sheet_by_name('Results (Exp_T)'); si=book.sheet_by_name('Inflow')
rawcsv={}
for group,fn in [('S','RS-S_caseD.csv'),('T','RS-T_caseD.csv')]:
 for r in csv.DictReader((A/fn).open(encoding='utf-8-sig')):
  if group=='T' and float(r['WD (deg)'])!=0:continue
  rawcsv[(group,str(int(r['No.'])))]=r
checks=[]
for k,r in meas.items():
 rr=rawcsv[k]; x,y,z=(float(r[c]) for c in ('x','y','z'))
 assert all(abs(a*400-b)<1e-7 for a,b in zip((float(rr['x[m]']),float(rr['y[m]']),float(rr.get('z[m]',rr.get('ｚ[m]')))),(x,y,z)))
 assert abs(float(rr['Vs[m/s]'])-float(r['Vs']))<1e-8
 s=sim[k];assert all(abs(a-b)<1e-7 for a,b in zip(s['luw_sample_xyz_m'],(x+850,y+550,gate['ground_wall_label_m']+z)))
 checks.append((k,float(r['Vs']),math.sqrt(sum(s[c]**2 for c in ('u_mps','v_mps','w_mps')))))
assert all(abs(float(si.cell_value(i,1))*0.001*400-float(x['z[m]'])*400)<1e-6 for i,x in enumerate(list(csv.DictReader((A/'AF_caseD.csv').open(encoding='utf-8-sig'))),start=3))
# Workbook header explicitly gives model units and velocity reference.
assert 'x[mm]' in str(ss.cell_value(2,1)) and 'UH' in str(ss.cell_value(0,7))
assert 'Scalar Velocity' in str(st.cell_value(3,4))
# S-points scalar versus mean vector in source.
sdiff=[]
for k,obs,vel in checks:
 if k[0]=='S':
  rr=rawcsv[k];vec=math.sqrt(sum(float(rr[c])**2 for c in ('U[m/s]','V[m/s]','W[m/s]')));sdiff.append(float(rr['Vs[m/s]'])-vec)
# Correlation and ratios are explicitly defined.
def pearson(a,b):
 am=statistics.mean(a);bm=statistics.mean(b);return sum((x-am)*(y-bm) for x,y in zip(a,b))/math.sqrt(sum((x-am)**2 for x in a)*sum((y-bm)**2 for y in b))
metrics={}
for group in ('S','T','all'):
 subset=[q for q in checks if group=='all' or q[0][0]==group];o=[q[1] for q in subset];v=[q[2] for q in subset]
 metrics[group]={'n':len(subset),'obs_mean_mps':statistics.mean(o),'sim_mean_mps':statistics.mean(v),'ratio_of_means':sum(v)/sum(o),'pearson_r':pearson(o,v)}
# Inlet prescribed profile, not a recovered measured mean field.
a=list(csv.DictReader((A/'AF_caseD.csv').open(encoding='utf-8-sig')));p=list(csv.DictReader((D/'CaseD/stage/caseD/wind_bc/profile.dat').open(),delimiter=' '))
assert len(a)==len(p)
profile=[]
for u,v in zip(a,p):
 profile.append({'AF_z_model_m':float(u['z[m]']),'LUW_z_agl_m':float(v['z']),'AF_U_mps':float(u['U[m/s]']),'deck_U_mps':float(v['U'])})
 assert abs(profile[-1]['AF_z_model_m']*400-profile[-1]['LUW_z_agl_m'])<1e-7 and abs(profile[-1]['AF_U_mps']-profile[-1]['deck_U_mps'])<1e-7
# Explicit unavailable-measurement markers.
e={'input_sha256':{str(f):sha(f) for f in [Z,F,B,A/'AF_caseD.csv',A/'RS-S_caseD.csv',A/'RS-T_caseD.csv',A/'LF_caseD.xls',A/'readme_caseD.md']},'source_mean_vtk_sha256_from_archive':data['source_vtk_sha256'],'archive_member_sha256':hashes,'profile_prescribed':profile,'profile_x2m_time_mean':None,'open_ground_2m_time_mean':None,'open_ground_to_inlet_ratio':None,'not_measured_reason':'Case D zip contains gate, point values and logs, not VTK fields or a longitudinal/open-ground profile; stopped Colab VM cannot be read back. A new VM cannot retrieve the terminated VM field without re-solving.','geometry':{'native_dims':gate['dims'],'origin':gate['origin'],'spacing':gate['spacing'],'wall_label_m':gate['ground_wall_label_m'],'gate_open_columns':gate['open_columns'],'roof_facet_count':len(tri),'n_triangles':n,'x_map':'x_LUW=x_C38+850','y_map':'y_LUW=y_C38+550','mapped_points':len(rows),'clamped':data['clamped'],'mixed':data['mixed'],'native_full_mask_archived':False},'observation':{'raw_csv_derived_rows_exact':len(checks),'workbook_S_velocity_header':ss.cell_value(2,10),'workbook_S_reference':ss.cell_value(0,7),'workbook_T_velocity_header':st.cell_value(3,4),'model_z_m':0.005,'fullscale_z_m':2,'S_Vs_minus_vector_magnitude_mean_mps':statistics.mean(sdiff),'S_Vs_minus_vector_magnitude_max_abs_mps':max(abs(x) for x in sdiff),'metric_definition':'ratio_of_means=sum(sim|mean vector|)/sum(raw Vs); Pearson r over matched rows','metrics':metrics},'solver_log_profile_lines':[line.strip() for line in log.splitlines() if any(s in line for s in ('Profile samples','Profile z range','Profile U range','STL bounds SI','Geometry        |','VK inlet target'))]}
(O/'evidence_v2.json').write_text(json.dumps(e,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'metrics':metrics,'S_scalar_vector_delta_mean':statistics.mean(sdiff),'S_scalar_vector_delta_max_abs':max(abs(x) for x in sdiff),'roofs':len(tri),'triangles':n,'profile_2m_prescribed':profile[0],'image':str(O/'points_roofs_gate_columns.png')},indent=2))
