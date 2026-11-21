"""MetPy diagnostics from all separately valid thermodynamic and wind RAOB levels."""
import json, numpy as np
from pathlib import Path
from metpy import calc as mc
from metpy.units import units
r=json.loads(Path('/content/convective_raob_raw.json').read_text())
out=[]
for event in r:
    pts=event['profiles'][0]['profile']
    tpts=sorted((q for q in pts if all(q.get(k) is not None for k in ('pres','tmpc','dwpc','hght')) and q['pres']>100 and q['dwpc']<=q['tmpc']),key=lambda q:-q['pres'])
    wpts=sorted((q for q in pts if all(q.get(k) is not None for k in ('pres','drct','sknt','hght')) and q['pres']>100),key=lambda q:q['hght'])
    # remove repeated pressures; observation data often includes mandatory and significant levels at same pressure.
    tpts=[q for i,q in enumerate(tpts) if i==0 or q['pres']<tpts[i-1]['pres']-.02]
    wpts=[q for i,q in enumerate(wpts) if i==0 or q['hght']>wpts[i-1]['hght']+.1]
    P=np.array([q['pres'] for q in tpts])*units.hPa;T=np.array([q['tmpc'] for q in tpts])*units.degC;D=np.array([q['dwpc'] for q in tpts])*units.degC
    heights=np.array([q['hght'] for q in wpts])*units.meter; pp=np.array([q['pres'] for q in wpts])*units.hPa
    dr=np.deg2rad(np.array([q['drct'] for q in wpts]));speed=np.array([q['sknt'] for q in wpts])*.514444
    U=-speed*np.sin(dr)*units('m/s');V=-speed*np.cos(dr)*units('m/s')
    row={'event_id':event['event_id'],'n_thermo':len(tpts),'n_wind':len(wpts),'source':event['url']}
    for name,fn in [('mucape',lambda:mc.most_unstable_cape_cin(P,T,D)[0].to('J/kg').magnitude),('dcape',lambda:mc.downdraft_cape(P,T,D)[0].to('J/kg').magnitude),('shear06',lambda:np.hypot(*[a.to('m/s').magnitude for a in mc.bulk_shear(pp,U,V,height=heights,bottom=heights[0],depth=6000*units.meter)]))]:
        try:row[name]=round(float(fn()),2)
        except Exception as e:row[name+'_error']=repr(e)
    out.append(row);print(row,flush=True)
Path('/content/convective_raob_full.jsonl').write_text(''.join(json.dumps(q)+'\n' for q in out))
print('RAOB_FULL_DONE',len(out))
