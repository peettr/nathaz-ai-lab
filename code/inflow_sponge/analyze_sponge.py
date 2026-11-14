from pathlib import Path
import csv,json,math
from PIL import Image, ImageDraw
R=Path(__file__).resolve().parent
old=list(csv.DictReader((R.parent/'approach_z0b/profiles_z0b.csv').open()))
orig={(float(q['x_m']),int(q['z_m'])):float(q['U_mps']) for q in old if q['tag']=='FGz2'}
prof={}; gates=[];flow=[];comparison=[]
for tag in ('FGz2r','FGz2ns'):
 rows=list(csv.DictReader((R/(tag+'_planes.csv')).open()))
 by={(int(q['x']),int(q['z_agl_m'])):q for q in rows}
 prof[tag]=by
 for x in (5,42,120,200,300,400):
  q=[by[(x,z)] for z in range(1,250) if (x,z) in by]
  # core physical 0..249 m; below z=1 and above 249 not covered by this integral.
  integ=sum((float(q[i]['ux_mps'])+float(q[i+1]['ux_mps']))/2 for i in range(len(q)-1))
  mint=sum((float(q[i]['rho_ux_lattice'])+float(q[i+1]['rho_ux_lattice']))/2 for i in range(len(q)-1))
  flow.append(dict(tag=tag,x=x,zmin=1,zmax=249,Qux_m2s=integ,Qrho_lattice=mint))
  for z in (2,5,10,16):
   official={2:2.964,5:3.2604,10:3.588,16:3.9286416}[z]
   p=by[(x,z)];u=float(p['U_mps']);gates.append(dict(tag=tag,x=x,z=z,U=u,official=official,bias_pct=100*(u/official-1),k=float(p['k_m2s2']),uw=float(p['uw_resolved_m2s2'])))
 for x in (5,42,120,200):
  for z in (2,5,10,20,30):
   if (x,z) in orig:
    u=float(by[(x,z)]['U_mps']);comparison.append(dict(tag=tag,x=x,z=z,U_full_y=u,U_old_11line=orig[(x,z)],difference_pct=100*(u/orig[(x,z)]-1)))
with (R/'gate_sponge.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=gates[0]);w.writeheader();w.writerows(gates)
with (R/'flux_sponge.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=flow[0]);w.writeheader();w.writerows(flow)
with (R/'repeat_old.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=comparison[0]);w.writeheader();w.writerows(comparison)
s={}
for x in (5,42,120,200,300,400):
 for z in (2,5,10,16,30,100,200,249,270,350,440):
  a=prof['FGz2r'].get((x,z));b=prof['FGz2ns'].get((x,z));
  if a and b:s[f'{x}:{z}']={'U_r':float(a['U_mps']),'U_ns':float(b['U_mps']),'delta_pct':100*(float(b['U_mps'])/float(a['U_mps'])-1),'k_r':float(a['k_m2s2']),'k_ns':float(b['k_m2s2'])}
(R/'summary.json').write_text(json.dumps({'paired':s,'flow':flow,'gates':gates},indent=2))
# Compact plot, full height and near-ground panel, speed against official table (provided profile file).
raw=[]
for line in (R/'stage_FGz2r/case/wind_bc/profile.dat').read_text().splitlines()[1:]:
 try:z,u=line.split();raw.append((float(z),float(u)))
 except:pass
im=Image.new('RGB',(1500,900),'white');d=ImageDraw.Draw(im)
colors={(tag,x):c for tag,cs in [('FGz2r',[(5,'#4d98be'),(200,'#1753a5'),(400,'#27345e')]),('FGz2ns',[(5,'#ffae56'),(200,'#d04927'),(400,'#8b182d')])] for x,c in cs}
for panel,(zmax,x0,y0,w,h) in enumerate(((450,100,50,630,780),(35,820,50,630,780))):
 d.rectangle((x0,y0,x0+w,y0+h),outline='black',width=2)
 umax=12 if zmax==450 else 5.5
 def coord(u,z):return x0+u/umax*w,y0+h-z/zmax*h
 for k in range(0,int(umax)+1,2):
  px,py=coord(k,0);d.line((px,y0,px,y0+h),fill='#eeeeee');d.text((px+3,y0+h-15),str(k),fill='black')
 for k in range(0,zmax+1,50 if zmax>100 else 5):
  px,py=coord(0,k);d.line((x0,py,x0+w,py),fill='#eeeeee');d.text((x0+3,py+2),str(k),fill='black')
 points=[coord(u,z) for z,u in raw if z<=zmax]
 if len(points)>1:d.line(points,fill='black',width=3)
 for tag in ('FGz2r','FGz2ns'):
  for x in (5,200,400):
   points=[coord(float(q['U_mps']),z) for (xx,z),q in sorted(prof[tag].items()) if xx==x and z<=zmax and z>=1]
   if len(points)>1:d.line(points,fill=colors[tag,x],width=3)
 d.text((x0+10,y0+12),'z<=%d m; horizontal axis U (m/s)'%zmax,fill='black')
for i,(name,c) in enumerate([('official','black')]+[(f'{tag} x={x}',colors[tag,x]) for tag in ('FGz2r','FGz2ns') for x in (5,200,400)]):
 d.rectangle((110+190*(i%7),840+20*(i//7),130+190*(i%7),850+20*(i//7)),fill=c)
 d.text((135+190*(i%7),838+20*(i//7)),name,fill='black')
im.save(R/'profiles_full_height.png')
print('rows',len(gates),len(flow),'plot',R/'profiles_full_height.png')
