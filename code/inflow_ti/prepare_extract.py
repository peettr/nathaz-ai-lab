from pathlib import Path
R=Path(__file__).resolve().parent
source=Path('./22_Lab/06_Logs/luw/run_r10_20261014/extract_a_r10.py').read_text()
old='return math.sqrt(sum(q*q for q in out)),max(tke,0.),fluid'
assert source.count(old)==1
source=source.replace(old,'return math.sqrt(sum(q*q for q in out)),max(tke,0.),fluid, out')
source=source.replace('speed,tke,nfluid=interp(*[v+s for v,s in zip(physical,shift)])','speed,tke,nfluid,uv=interp(*[v+s for v,s in zip(physical,shift)])')
source=source.replace("'fluid_corners':nfluid}","'fluid_corners':nfluid,'mean_velocity_mps':uv}")
source=source.replace('interp(x,float(y),z)[0]','interp(x,float(y),z)[0]')
key=' m.close()\nout={'
assert source.count(key)==1
extra=''' # Upwind profiles: y=100..400 every 30 m, single same-height cross-section.
 profiles=[]
 for xsite in (5.,25.,42.):
  for zagl in range(1,31):
   vals=[interp(xsite,float(y),float(zagl)) for y in range(100,401,30)]
   profiles.append({'x':xsite,'z_agl':zagl,'U_mps':sum(v[0] for v in vals)/len(vals),
     'k_m2s2':sum(v[1] for v in vals)/len(vals),'n':len(vals)})
 # Point 50: west-to-east transect at the actual registered y, z=2m.
 street=[]
 y50=-45.0+1000.60004-750+dx
 for xsite in range(175,241):
  s,k,f,v=interp(float(xsite),y50,2.0)
  street.append({'x':xsite,'y':y50,'ux':v[0],'uy':v[1],'speed':s,'k':k,'fluid_corners':f})
'''
source=source.replace(key,extra+key)
source=source.replace("'upstream':upstream,'uref':points['uref']}","'upstream':upstream,'profiles':profiles,'street50':street,'uref':points['uref']}")
(R/'extract_ti.py').write_text(source)
print('extractor generated',len(source))
