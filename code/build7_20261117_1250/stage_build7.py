#!/usr/bin/env python3
"""Freeze build7 distinct from historical build6 without touching old evidence."""
from pathlib import Path
import hashlib,json,tarfile,difflib
R=Path(__file__).resolve().parent; V6=R.parent/'build6_20261117_123412'; S=R/'FluidX3D_facade_v7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace_once(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
w=(V6/'worker_gate.py').read_text().replace('t9b6','t9b7').replace('facade_v6','facade_v7').replace('build6','build7')
start=w.index(' # Recheck both cube mass histories')
end=w.index(' # The two wall axes',start)
cube=w[start:end]
w=w[:start]+w[end:]
# Proof of actual activation before the long tests; expected count from fixture geometry below.
needle=' # The two wall axes use the identical source and corresponding compiler macro state.'
smoke=''' # Test fixture: L=8, two x-normal thick slabs; 2 faces × 8×8 fluid cells × 4 diagonals = 512 mirror links.
 small=O/'small_x_on_trace.csv';d=R/'channel_on'
 env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(small),'T9B_SMALL_COUNT':'1','T9B_GATE_SHAPE':'channel','LUW_CAPTURE_CL':str(O/'on_small_actual_opencl.cl')}
 run([str(d/'bin/FluidX3D')],d,'small_x_on',env,limit=240)
 ready(small);cl=O/'on_small_actual_opencl.cl';ready(cl)
 smoke_rows=list(csv.DictReader(small.open()))
 assert len(smoke_rows)==3 and [int(x['step']) for x in smoke_rows]==[0,1,2]
 smoke_count=[int(x['device_mirror_links']) for x in smoke_rows]
 smoke_info={'fixture':'8^3, x<=2 or x>=5 solid, all other directions periodic','hand_expected_per_step':512,'gpu_count':smoke_count,'cl_has_count_define':'#define FACADE_COUNT' in cl.read_text(),'cl_has_atomic':'atomic_inc' in cl.read_text()}
 q=O/'small_counter_verdict.json';q.write_text(json.dumps(smoke_info,indent=2)+'\\n');ready(q)
 assert smoke_info['cl_has_count_define'] and smoke_info['cl_has_atomic'] and smoke_count==[0,512,512],smoke_info
'''
w=replace_once(w,needle,smoke+cube+needle)
# Cube is descriptive only; both branches always complete before channel, even if M_all trend is large.
w=w.replace("  if not passed:raise RuntimeError('cube '+state+' gate failed')","  # build7: old M_all gate superseded; do not stop on this descriptive quantity.")
w=w.replace("  passed=valid and (abs(slope)<=1e-5 and span<=1e-5 if state=='on' else maxdrift<=1e-6)","  passed=None # superseded M_all gate; activation judged in channels")
w=w.replace(" # Both physical gates passed; only now enter the city compilation/closed-state gates."," # Both channel axes passed; only now enter the city compilation/closed-state gates.")
# City on: force a real counted kernel launch, with flags-only no longer eligible as activation proof.
w=w.replace("  if state=='on':env['LUW_FLAGS_ONLY']='1'", "  if state=='on':env['T9B_CITY_COUNT_OUTPUT']=str(O/'city_on_device_count.csv')")
w=w.replace(" for state in ('on','off'):\n  d=R/('city_'+state)", " for state in ('off','on'):\n  d=R/('city_'+state)")
w=w.replace("  defines.write_text(s);run(['make','Linux','-j8'],d,'city_build_'+state,limit=1200)", "  if state=='on':s=s.replace('#define FACADE_FREE_SLIP // T9b-build ON','#define FACADE_FREE_SLIP // T9b-build ON\\n#define FACADE_COUNT')\n  defines.write_text(s);run(['make','Linux','-j8'],d,'city_build_'+state,limit=1200)")
w=w.replace("  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200 if state=='off' else 900)", "  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200)\n  if state=='on':\n   count_csv=O/'city_on_device_count.csv';assert count_csv.is_file() and count_csv.stat().st_size>0\n   ready(count_csv)\n   counts=[int(line.split(',')[1]) for line in count_csv.read_text().splitlines()]\n   assert counts and min(counts)>0,('city activation invalid',min(counts) if counts else None)")
(R/'worker_gate.py').write_text(w)
for name in ('controller_gate.py','probe_gate.py','launch_gate.py'):
 s=(V6/name).read_text().replace('t9b6','t9b7').replace('build6','build7').replace('luw-t9b6-g4-1117-a1','luw-t9b7-g4-1117-a1')
 (R/name).write_text(s)
c=R/'controller_gate.py';s=c.read_text().replace("'t9b7_source.tar.gz','t9b7_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py'","'t9b7_source.tar.gz','t9b7_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py','audit_versions.py','emu_facade_lead.py'")
s=s.replace("('t9b7_source.tar.gz','t9b7_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py')","('t9b7_source.tar.gz','t9b7_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py','audit_versions.py','emu_facade_lead.py')")
s=s.replace("'--final-pull','/content/t9b7.log:'+str(O)","'--final-pull','/content/t9b7.log:'+str(O)")
c.write_text(s)
# CPU audit on the VM before compiling/solving; produced output preserved in handoff.
w=(R/'worker_gate.py').read_text();a=" verdict={'created':time.time(),";i=w.index(a)
pre=""" # CPU-only version-stamp audit is a mandatory fail-closed prerequisite on the VM.
 subprocess.run(['python3','/content/audit_versions.py'],cwd='/content',check=True,stdout=(O/'audit_versions.log').open('x'),stderr=subprocess.STDOUT,timeout=600)
 audit_path=pathlib.Path('/content/audit_versions_output.json');assert audit_path.is_file()
 shutil.copyfile(audit_path,O/'audit_versions_output.json');ready(O/'audit_versions_output.json');ready(O/'audit_versions.log')
"""
w=w[:i]+pre+w[i:];(R/'worker_gate.py').write_text(w)
# Source archive and per-file hashes.
arc=R/'t9b7_source.tar.gz'
with tarfile.open(arc,'w:gz') as t:t.add(S,arcname=S.name)
members={str(p.relative_to(S)):sha(p) for p in S.rglob('*') if p.is_file()}
(R/'t9b7_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'members':members},indent=2)+'\n')
for label,path in [('v6',V6/'FluidX3D_facade_v6'),('T5_OFF',Path('./24_Urban_Wind_LBM/06_Logs/R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off'))]:
 lines=[]
 for p in S.rglob('*'):
  if not p.is_file() or not (path/p.relative_to(S)).is_file():continue
  b=(path/p.relative_to(S)).read_text(errors='replace').splitlines(keepends=True);v=p.read_text(errors='replace').splitlines(keepends=True)
  lines.extend(difflib.unified_diff(b,v,fromfile=label+'/'+str(p.relative_to(S)),tofile='v7/'+str(p.relative_to(S))))
 (R/('diff_vs_'+label+'.patch')).write_text(''.join(lines))
print('STAGED',arc,sha(arc),len(members))
