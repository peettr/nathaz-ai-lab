from pathlib import Path
import csv,json,math,statistics
b=Path(__file__).resolve().parent
rows=list(csv.DictReader((b/'mixing07_stress_samples.csv').open())); d=json.loads((b/'mixing07_profile.json').read_text())
assert len(rows)==450 and set(int(r['n']) for r in rows)=={500}
wall=list(csv.DictReader(__import__('io').StringIO(d['wall_tau_csv'])))
uconv=statistics.median(float(r['ustar_mps'])/math.sqrt(float(r['tau_abs_over_rho_lattice'])) for r in wall)
assert 50<uconv<60,uconv
ustar=.2418545;z0=.024;k=.4
out=[]
for x in (200,300,400):
 for z in range(1,31):
  a=[r for r in rows if int(r['x'])==x and int(r['z'])==z];assert len(a)==5
  u=statistics.mean(float(r['u_lu']) for r in a)*uconv
  w=statistics.mean(float(r['w_lu']) for r in a)*uconv
  uw=statistics.mean(float(r['uw_lu']) for r in a)*uconv*uconv
  reyn=w*u-uw
  nut=statistics.mean(float(r['nut_lu']) for r in a)*uconv
  def mean(zp):return statistics.mean(float(r['u_lu']) for r in rows if int(r['x'])==x and int(r['z'])==zp)*uconv
  grad=(mean(z+1)-mean(z-1))/2 if z>1 and z<30 else (mean(z+1)-mean(z) if z==1 else mean(z)-mean(z-1))
  sgs=nut*grad; molecular=1.48e-5*grad
  out.append(dict(x=x,z=z,u=u,w=w,uw=uw,resolved=reyn,nut=nut,gradient=grad,sgs=sgs,molecular=molecular,total=reyn+sgs+molecular,ratio_actual=None,ratio_target=(reyn+sgs+molecular)/ustar**2))
wall=list(csv.DictReader(__import__('io').StringIO(d['wall_tau_csv'])));actual={x:statistics.mean(float(r['tau_abs_over_rho_lattice']) for r in wall if int(r['x'])==x)*uconv*uconv for x in (200,300,400)}
for r in out:r['ratio_actual']=r['total']/actual[r['x']]
with (b/'mixing07_stress_profile.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=out[0]);writer.writeheader();writer.writerows(out)
summary={str(x):{'actual_tau':actual[x],'points':{str(z):next(r for r in out if r['x']==x and r['z']==z) for z in (1,2,3,4,5,10,20,30)},'u2_ratio_original':next(r['ratio'] for r in d['rows'] if r['x']==x and r['z']==2),'u2_ratio_shifted_reference':next(r['ratio'] for r in d['rows'] if r['x']==x and r['z']==2)*math.log((2+z0)/z0)/math.log((1.5+z0)/z0)} for x in actual}
(b/'mixing07_stress_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
