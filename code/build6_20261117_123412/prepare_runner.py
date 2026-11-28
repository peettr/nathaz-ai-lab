#!/usr/bin/env python3
"""Prepare build6 worker/controller without reusing build5 run state."""
from pathlib import Path
import tarfile,hashlib,json,shutil
R=Path(__file__).resolve().parent
OLD=R.parent/'build5_20261117_1156'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=R/'FluidX3D_facade_v6'
arc=R/'t9b6_source.tar.gz'
with tarfile.open(arc,'w:gz') as tar:tar.add(source,arcname=source.name)
members={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
(R/'t9b6_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'members':members},indent=2)+'\n')
for name in ('worker_gate.py','controller_gate.py','probe_gate.py','launch_gate.py'):
 s=(OLD/name).read_text()
 s=s.replace('t9b5','t9b6').replace('T9b build5','T9b build6').replace('build5','build6').replace('facade_v5','facade_v6').replace('luw-t9b5-g4-1117-a1','luw-t9b6-g4-1117-a1')
 if name=='worker_gate.py':
  # The changed eligibility requires another cube test; enforce cube before channels.
  s=s.replace("'cube_build4_previously_passed':True,", "'cube_build6_retested':True,")
  s=s.replace("(needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON')+'\\n#define FACADE_CUBE_GATE'", "(needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON')+'\\n#define FACADE_CUBE_GATE\\n#define FACADE_COUNT'")
  s=s.replace(" # The two wall axes use the identical source and corresponding compiler macro state.",""" # Recheck both cube mass histories after the eligibility change, before channel tests.
 import numpy as np
 cube={}
 for state in ('off','on'):
  d=R/('channel_'+state);p=O/('cube_'+state+'_trace.csv')
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(p)}
  run([str(d/'bin/FluidX3D')],d,'cube_'+state,env,limit=1000)
  ready(p);rows=list(csv.DictReader(p.open()))
  assert len(rows)==301 and [int(r['step']) for r in rows]==list(range(301))
  mass=np.array([float(r['M_all']) for r in rows]);ref=mass[50]
  assert ref>0 and np.all(np.isfinite(mass))
  rel=(mass[50:]-ref)/ref
  slope=float(np.polyfit(np.arange(50,301),rel,1)[0])*1000
  span=float(np.ptp(rel)); maxdrift=float(np.max(np.abs(rel)))
  active=[int(r['device_mirror_links']) for r in rows]
  valid=(min(active[1:])>0 if state=='on' else max(active)==0)
  passed=valid and (abs(slope)<=1e-5 and span<=1e-5 if state=='on' else maxdrift<=1e-6)
  cube[state]={'init_jump':float((mass[1]-mass[0])/mass[0]),'trend_x1000':slope,'amplitude':span,'max_drift_after_50':maxdrift,'min_device_links':min(active[1:]),'max_device_links':max(active),'activation_valid':valid,'passed':passed}
  verdict['cube']=cube;q=O/('gate_verdict_cube_'+state+'.json');q.write_text(json.dumps(verdict,indent=2)+'\\n');ready(q)
  if not passed:raise RuntimeError('cube '+state+' gate failed')
 # The two wall axes use the identical source and corresponding compiler macro state.""")
  s=s.replace("r['mirror_active_cells']","r['device_mirror_links']")
  # A zero count is an invalid test, not a physics fail.
  s=s.replace("'passed':ok}","'passed':ok,'classification':'无效测试' if state=='on' and not valid else ('通过' if ok else '不通过')}")
  s=s.replace("# Both physical gates passed; only now enter the city compilation/closed-state gates.","# Both physical gates passed; only now enter the city compilation/closed-state gates.")
  # Counters disabled in city builds; no influence on frozen off sha.
  s=s.replace("  for axis in range(3):\n   sl=[slice(None)]*3;sl[axis]=slice(0,2);elig[tuple(sl)]=False\n   sl=[slice(None)]*3;sl[axis]=slice(-2,None);elig[tuple(sl)]=False\n","")
  s=s.replace("  multi=fluid&(ns>=2);mirror=", "  oldelig=elig.copy()\n  for axis in range(3):\n   sl=[slice(None)]*3;sl[axis]=slice(0,2);oldelig[tuple(sl)]=False\n   sl[axis]=slice(-2,None);oldelig[tuple(sl)]=False\n  multi=fluid&(ns>=2);mirror=")
  s=s.replace("  coverage={'multi_normal_native_bounce':", "  coverage={'eligible_cells_new_minus_old':int(elig.sum()-oldelig.sum()),'multi_normal_native_bounce':")
  s=s.replace("'mirror_links':links,", "'mirror_links':links,'mirror_cells_old_estimate':None,")
  # Explicitly retain a comparable pre-change mirror mask calculation, not just eligibility count.
  s=s.replace("  ids={31,39", "  oldmirror=np.zeros(A.shape,dtype=bool)\n  for axis,sgn in ((2,1),(2,-1),(1,1),(1,-1)):\n   normal=np.roll(solid,-sgn,axis=axis);face=oldelig&normal\n   for tangaxis in (0,1,2):\n    if tangaxis==axis:continue\n    for tang in (-1,1):\n     valid=face&np.roll(oldelig,tang,axis=tangaxis)&np.roll(normal,tang,axis=tangaxis)&np.roll(np.roll(solid,tang,axis=tangaxis),-sgn,axis=axis)\n     oldmirror|=valid\n  ids={31,39")
  s=s.replace("'mirror_cells_old_estimate':None,","'mirror_cells_old_estimate':int(oldmirror.sum()),'mirror_cells_new_minus_old':int(mirror.sum()-oldmirror.sum()),")
  # Include city solver MLUPs from exact solver logs as raw lines (not fabricated).
  s=s.replace("  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200 if state=='off' else 900)","  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200 if state=='off' else 900)\n  import re\n  ml=[line.strip() for line in (O/('city_solver_'+state+'.log')).read_text(errors='replace').splitlines() if re.search(r'MLUPs',line,re.I)]\n  perf=O/('city_'+state+'_mlups.json');perf.write_text(json.dumps({'state':state,'raw_mlups_lines':ml[-10:]})+'\\n');ready(perf)")
 if name=='controller_gate.py':
  s=s.replace('3.55*3600/6.81','3.55*3600/6.81')
  s=s.replace("'--max-hours','1'","'--max-hours','1'")
 (R/name).write_text(s)
print(R,sha(arc),len(members))
