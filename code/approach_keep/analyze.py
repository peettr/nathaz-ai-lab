"""Offline-only reduction of previously downloaded compact outputs."""
from pathlib import Path
import csv,json,math,statistics
R=Path(__file__).resolve().parent
old=R.parents[1]/'wp1b_ibm/resolution_split/profiles_five_stations.csv'
rows=list(csv.DictReader(old.open()));d=json.loads((R/'E1G0_offset_samples_a_r10.json').read_text())
allrows=[]
for r in rows:
 if r['tag'] in ('E1','E05') and r['availability']=='measured':allrows.append({'tag':r['tag'],'x_m':float(r['x_m']),'z_m':float(r['z_m']),'U_mps':float(r['U_mps']),'k_m2s2':float(r['k_m2s2'])})
for p in d['profiles']:allrows.append({'tag':'E1G0','x_m':p['x'],'z_m':p['z_agl'],'U_mps':p['U_mps'],'k_m2s2':p['k_m2s2']})
with (R/'profiles_approach.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=allrows[0].keys());w.writeheader();w.writerows(allrows)
by={(r['tag'],r['x_m'],r['z_m']):r for r in allrows}
ref={}
for z in (2.,5.,10.,15.9):
 for tag in ('E1','E05','E1G0'):
  if z==15.9:
   # Archived E1/E05 upstream data use identical interpolation at physical z=15.9.
   if tag=='E1G0':q=d['upstream']
   else:
    p=R.parents[1]/'wp1b_ibm/resolution_split'/f'{tag}_samples.json'
    q=json.loads(p.read_text())['upstream']
   a={r['x_local_m']:r['mean_speed_mps'] for r in q if abs(r['z_m']-z)<1e-5}
   v5,v42=a[5.],a[42.]
  else:
   v5=by[tag,5.,z]['U_mps'];v42=by[tag,42.,z]['U_mps']
  e05 = ( {r['x_local_m']:r['mean_speed_mps'] for r in json.loads((R.parents[1]/'wp1b_ibm/resolution_split/E05_samples.json').read_text())['upstream'] if abs(r['z_m']-z)<1e-5}[42.] if z==15.9 else by['E05',42.,z]['U_mps'])
  ref.setdefault(tag,{})[str(z)]={'U5':v5,'U42':v42,'retention':v42/v5,'vs_E05_pct':100*(v42/e05-1)}
tau=[]
for x in csv.DictReader((R/'E1G0_wall_tau_actual.csv').open()):
 if int(x['y']) in range(100,311,30) and int(x['x']) in (5,15,25,35,42):tau.append(x)
for x in (5,15,25,35,42):
 a=[float(r['tau_abs_over_rho_lattice']) for r in tau if int(r['x'])==x]
 if a:ref['E1G0'].setdefault('ustar_mps',{})[str(x)]=statistics.mean(float(r['ustar_mps']) for r in tau if int(r['x'])==x)
 # Calculate mean tau then convert if requested; spatial mean of ustar differs from sqrt(mean tau).
print(json.dumps(ref,indent=2));(R/'summary.json').write_text(json.dumps(ref,indent=2)+'\n')
