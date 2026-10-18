from pathlib import Path
import csv, math, hashlib, tarfile, shutil, json
R=Path(__file__).resolve().parent
S=R.parent/'inflow_sponge/stage_FGz2r'
C=R.parent/'city_z0/stage'
plane={(int(r['x']),int(r['z_agl_m'])):float(r['U_mps']) for r in csv.DictReader((R.parent/'inflow_sponge/FGz2r_planes.csv').open())}
raw=[]
for line in (S/'case/wind_bc/profile.dat').read_text().splitlines()[1:]:
 z,u=line.split();raw.append((float(z),float(u)))
def interp(z):
 if z<=raw[0][0]:return raw[0][1]
 if z>=raw[-1][0]:return raw[-1][1]
 for (a,u),(b,v) in zip(raw,raw[1:]):
  if a<=z<=b:return u+(v-u)*(z-a)/(b-a)
 raise ValueError(z)
# Symmetric five-metre box smoothing in log correction, no fitted free parameter.
logs={z:math.log(interp(z)/plane[200,z]) for z in range(1,250)}
rows=[]
for z in range(1,250):
 lo=max(1,z-2);hi=min(249,z+2)
 smooth=sum(logs[k] for k in range(lo,hi+1))/(hi-lo+1)
 taper=1 if z<=200 else (1-(z-200)/50)**2*(1+2*(z-200)/50)
 factor=math.exp(smooth*taper)
 rows.append(dict(z=z,official=interp(z),fgz2r=plane[200,z],raw_factor=math.exp(logs[z]),smoothed_factor=factor,U_new=interp(z)*factor))
# Explicit continuous return to original at the 250m table top.
rows.append(dict(z=250,official=interp(250),fgz2r=plane[200,249],raw_factor=1,smoothed_factor=1,U_new=interp(250)))
with (R/'factors.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
profile='z,U\n'+''.join(f"{r['z']}\t{r['U_new']:.9f}\n" for r in rows)
(R/'profile_corrected.dat').write_text(profile)
for tag,src in [('FGz2c',S),('Gz2c',C)]:
 dest=R/('stage_'+tag)
 assert not dest.exists(),dest
 shutil.copytree(src,dest,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 (dest/'case/wind_bc/profile.dat').write_text(profile)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp']
 manifest={'tag':tag,'z0':.002,'a':0,'files':{p:hashlib.sha256((dest/p).read_bytes()).hexdigest() for p in files}}
 (R/(tag+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(dest/'FluidX3D',arcname='FluidX3D');t.add(dest/'case',arcname='case')
 print(tag,manifest)
print('factors 2/5/10/16/200/249',[(r['z'],r['smoothed_factor']) for r in rows if r['z'] in (2,5,10,16,200,249)])
