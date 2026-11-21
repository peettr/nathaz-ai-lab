#!/usr/bin/env python3
"""Fresh build8: preserve build7, repair diagnostic counter only."""
from pathlib import Path
import shutil,re,difflib,json,hashlib,tarfile
R=Path(__file__).resolve().parent; P=R.parent/'build7_20261117_1250'; V=R/'FluidX3D_facade_v8';shutil.copytree(P/'FluidX3D_facade_v7',V)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
k=V/'src/kernel.cpp';s=k.read_text();old='#ifdef FACADE_COUNT\n      atomic_inc((volatile global uint*)facade_link_count);\n#endif';new=')+"#ifdef FACADE_COUNT"+R(\n      atomic_inc((volatile global uint*)facade_link_count);\n)+"#endif"+R(';assert s.count(old)==16,s.count(old);s=s.replace(old,new);k.write_text(s)
# Keep disabled kernel source byte-identical to T5 by host-guarding every added fragment.
s=k.read_text();a=')+"#ifdef FACADE_FREE_SLIP"+R(\n// A single flat horizontal facade normal;';assert s.count(a)==1;s=s.replace(a,')\n#ifdef FACADE_FREE_SLIP\n+"#ifdef FACADE_FREE_SLIP"+R(\n// A single flat horizontal facade normal;',1)
b=')+"#endif"+R(\n)+R(kernel void stream_collide)';assert s.count(b)==1;s=s.replace(b,')+"#endif"\n#endif\n+R(\n)+R(kernel void stream_collide)',1)
c=')+"#ifdef FACADE_FREE_SLIP"+R(\n  // Every mirror read';assert s.count(c)==1;s=s.replace(c,')\n#ifdef FACADE_FREE_SLIP\n+"#ifdef FACADE_FREE_SLIP"+R(\n  // Every mirror read',1)
d=')+"#endif"+R(\n)+"#ifdef GROUND_WALL_MODEL"';assert s.count(d)==1;s=s.replace(d,')+"#endif"\n#endif\n+R(\n)+"#ifdef GROUND_WALL_MODEL"',1)
e=')+"#ifdef FACADE_COUNT"+R(\n    , global uint* facade_link_count\n)+"#endif"+R(\n)';assert s.count(e)==1;s=s.replace(e,')\n#ifdef FACADE_FREE_SLIP\n+"#ifdef FACADE_COUNT"+R(\n    , global uint* facade_link_count\n)+"#endif"\n#endif\n+R(\n)',1)
k.write_text(s)
# Clone controller/worker/probes; no repeat of already completed CPU audit.
for n in ['controller_gate.py','worker_gate.py','launch_gate.py','probe_gate.py']:
 s=(P/n).read_text().replace('t9b7','t9b8').replace('build7','build8').replace('facade_v7','facade_v8').replace('luw-t9b7-g4-1117-a1','luw-t9b8-g4-1117-a1')
 if n=='worker_gate.py':
  a=s.index(' # CPU-only version-stamp audit');b=s.index(' verdict=',a);s=s[:a]+s[b:]
  s=s.replace("'cube_build8_retested':True,", "'cube_build8_retested':True,")
  a=s.index(' # Test fixture:');b=s.index(' # Recheck both cube',a)
  s=s[:a]+''' # Small-box on and off, each with step 0 initialization and 1/2 measured launches.
 for state in ('on','off'):
  small=O/('small_x_'+state+'_trace.csv');d=R/('channel_'+state)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(small),'T9B_SMALL_COUNT':'1','T9B_GATE_SHAPE':'channel','LUW_CAPTURE_CL':str(O/(state+'_small_actual_opencl.cl'))}
  run([str(d/'bin/FluidX3D')],d,'small_x_'+state,env,limit=240)
  ready(small);cl=O/(state+'_small_actual_opencl.cl');ready(cl)
  rows=list(csv.DictReader(small.open()));assert len(rows)==3 and [int(x['step']) for x in rows]==[0,1,2]
  counts=[int(x['device_mirror_links']) for x in rows]
  info={'state':state,'fixture':'8^3 x<=2 or x>=5 solid','expected_steps_1_2':512 if state=='on' else 0,'observed':counts,'atomic_occurrences':cl.read_text().count('atomic_inc(')}
  q=O/('small_'+state+'_verdict.json');q.write_text(json.dumps(info,indent=2)+'\\n');ready(q)
  assert counts==([0,512,512] if state=='on' else [0,0,0]) and (info['atomic_occurrences']==16 if state=='on' else info['atomic_occurrences']==0),info
''' +s[b:]
  # Check channel physics before descriptive cube and before city.
  a=s.index(' # Recheck both cube');b=s.index(' # The two wall axes',a);cube=s[a:b];s=s[:a]+s[b:];a=s.index(' # Both channel axes passed');s=s[:a]+cube+s[a:]
  # prevent misleading v5 count comparison (build7 oldelig is identical to elig).
  s=s.replace("  oldelig=elig.copy()", "  oldelig=elig.copy() # v5 coverage must be separately reconstructed; this is not v5")
 if n=='controller_gate.py':
  s=s.replace("'audit_versions.py','emu_facade_lead.py'",'')
  s=s.replace("'probe_gate.py',)","'probe_gate.py')")
 (R/n).write_text(s)
# Archive source; no overwrite of historical roots.
arc=R/'t9b8_source.tar.gz'
with tarfile.open(arc,'w:gz') as t:t.add(V,arcname=V.name)
members={str(p.relative_to(V)):sha(p) for p in V.rglob('*') if p.is_file()};(R/'t9b8_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'members':members},indent=2)+'\n')
lines=[]
for p in V.rglob('*'):
 if not p.is_file():continue
 prev=P/'FluidX3D_facade_v7'/p.relative_to(V)
 if prev.is_file() and prev.read_bytes()!=p.read_bytes():lines+=list(difflib.unified_diff(prev.read_text().splitlines(keepends=True),p.read_text().splitlines(keepends=True),fromfile='v7/'+str(p.relative_to(V)),tofile='v8/'+str(p.relative_to(V))))
(R/'diff_vs_v7.patch').write_text(''.join(lines));print('STAGED',sha(arc),len(members),'diff_lines',len(lines))
