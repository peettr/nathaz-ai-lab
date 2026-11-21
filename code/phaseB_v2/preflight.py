#!/usr/bin/env python3.10
"""No GPU allocation: test exact controller timeout branch and stage contracts."""
import importlib.util,pathlib,tempfile,subprocess,json,hashlib,tarfile,sys,os
R=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('phaseb_v2_controller',R/'controller.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
archive=R/'stage_phase.tar.gz';assert c.sha(archive)==json.loads((R/'archive.json').read_text())['sha256']
with tarfile.open(archive) as t:
 names=t.getnames();assert 'stage/phase_manifest.json' in names
 assert all(n=='stage' or n.startswith('stage/') for n in names)
man=json.loads((R/'stage/phase_manifest.json').read_text())
for n,h in man['source_on'].items():assert c.sha(R/'stage/FluidX3D_on/src'/n)==h
for seed in (107,108,109):
 case=f'dx1p0_s{seed}';assert c.sha(R/'stage'/case/'conf.luwpf')==man['cases'][case]['conf_sha256']
for n in ('worker.py','launch.py','probe.py','controller.py','ack.py','analyze_B.py'):
 subprocess.run([sys.executable,'-m','py_compile',str(R/n)],check=True)
print('IMPORT_AND_ARCHIVE_PASS',len(names),flush=True)
# Exercise the exact monitor_once method, not a surrogate loop. No real stop permitted.
events=[];c.log=lambda kind,**k:events.append((kind,k))
c.cmd=lambda *a,**kw:('IDLE named session',0)
c.stop=lambda reason: (_ for _ in ()).throw(AssertionError('UNEXPECTED STOP '+reason))
c.ENDPOINT='gpu-a100-s-test'
def timeout():raise subprocess.TimeoutExpired('read-only probe',110)
state,absent=c.monitor_once(timeout,lambda:(True,'gpu-a100-s-test'),lambda _:None)
assert state is None and not absent and [v[0] for v in events]==['probe_error','named_status','global_reconcile']
print('PROBE_TIMEOUT_CONTINUES',json.dumps(events),flush=True)
# Exact ACK script against a temporary stand-in /content tree, tested with expected sha and no solver.
with tempfile.TemporaryDirectory(dir=R) as d:
 p=pathlib.Path(d);(p/'B_dx1p0_s107_thin.sha256').write_text('a'*64)
 source=(R/'ack.py').read_text().replace("pathlib.Path('/content/phaseb_out')","pathlib.Path("+repr(str(p))+")")
 out=subprocess.run([sys.executable,'-c',source],env={**os.environ,'ACK_LABEL':'B_dx1p0_s107','ACK_SHA':'a'*64},capture_output=True,text=True,check=True)
 assert 'ACK B_dx1p0_s107' in out.stdout and (p/'B_dx1p0_s107.ack').read_text()=='a'*64
 print('ACK_PASS',out.stdout.strip(),flush=True)
# Test existing thin-field reference comparator and plotting-module imports without running a solver.
spec=importlib.util.spec_from_file_location('analysis',R/'analyze_B.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
base=R.parent.parent/'R21.4a_T3_emptyground/T3d'
for seed in (107,108,109):
 for grid in ('1p0','0p5'):
  m=json.loads((base/f'dx{grid}_s{seed}_metrics_wall_corrected.json').read_text())
  assert m['xc_G2_mps'] and m['inlet_G2_at_x5_mps']
print('ANALYSIS_IMPORT_AND_REFERENCE_PASS',flush=True)
