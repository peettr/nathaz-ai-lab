#!/usr/bin/env python3
"""只读输入；以 AIJ/Zenodo AF 和冻结源码复核入口设计等效 TI。"""
from pathlib import Path
import csv, io, json, math, urllib.request, hashlib
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
AF='https://zenodo.org/records/15429018/files/AF_caseE.csv?download=1'
raw=urllib.request.urlopen(AF,timeout=20).read()
rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
obs=[(float(r['z(m)']),float(r['U(m/s)']),float(r['k(m2/s2)'])) for r in rows]
profile=BASE/'06_Logs/R21.4a_T5_caseE_WM_retry1/stage/case/wind_bc/profile.dat'
pdat=[tuple(map(float,l.split())) for l in profile.read_text().splitlines()[1:]]
assert len(obs)==len(pdat)==12
assert all(abs(z-zp)<1e-9 and abs(u-up)<0.001 for (z,u,k),(zp,up) in zip(obs,pdat))
src=BASE/'06_Logs/R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off/src/setup.cpp'
text=src.read_text()
assert 'cfg.official_sigma_scale = units.u(7.8f)' in text
assert 'cfg_.official_sigma_scale*sqrtf(2.0f*kvar/3.0f)' in text
import re
zm=re.search(r'static constexpr float zk\[\] = \{([^}]+)\}',text)
km=re.search(r'static constexpr float kr\[\] = \{([^}]+)\}',text)
def floats(m): return [float(x.strip().rstrip('f')) for x in m.group(1).split(',')]
zk,kr=floats(zm),floats(km)
assert len(zk)==len(kr)==len(obs)
assert all(abs(z-zk[i])<1e-9 and abs(k/7.8**2-kr[i])<1e-5 for i,(z,u,k) in enumerate(obs))
def lerp(z,tab):
 if z<=tab[0][0]: return tab[0][1]
 if z>=tab[-1][0]: return tab[-1][1]
 for (a,va),(b,vb) in zip(tab,tab[1:]):
  if a<=z<=b:return va+(vb-va)*(z-a)/(b-a)
 raise AssertionError(z)
out=[]
for z in [2,5,10,15.9,25,50]:
 U=lerp(z,[(x,u) for x,u,k in obs]); k=lerp(z,[(x,v) for x,u,v in obs])
 Up=lerp(z,pdat); krz=lerp(z,list(zip(zk,kr)))
 sigma_obs=math.sqrt(2*k/3); sigma_set=7.8*math.sqrt(2*krz/3)
 # Equivalent 1-component TI only under isotropic assumption, not a measured longitudinal TI.
 out.append(dict(z_m=z,U_obs_mps=U,k_obs_m2s2=k,U_profile_mps=Up,
       TI_equiv_obs_pct=100*sigma_obs/U,TI_equiv_set_pct=100*sigma_set/Up,
       TI_equiv_difference_pp=100*(sigma_set/Up-sigma_obs/U),
       sigma_obs_mps=sigma_obs,sigma_set_mps=sigma_set,
       fixed_conf_ti_pct=16.21087892))
with (ROOT/'comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
obj=dict(source_url=AF,source_sha256=hashlib.sha256(raw).hexdigest(),profile_path=str(profile),profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(),setup_path=str(src),setup_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),method='TI_eq(z)=sqrt(2*k(z)/3)/U(z); isotropic equivalent, not measured longitudinal TI. Linear interpolation in z for U and k; setup interpolates k/UR². Target sigma=7.8*sqrt(2*k_norm/3).',rows=out)
(ROOT/'comparison.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
for r in out:print(f"{r['z_m']:5g} {r['TI_equiv_obs_pct']:.6f} {r['TI_equiv_set_pct']:.6f} {r['TI_equiv_difference_pp']:+.6f}")
print('AF SHA256',obj['source_sha256'])
print('source setup SHA256',obj['setup_sha256'])
