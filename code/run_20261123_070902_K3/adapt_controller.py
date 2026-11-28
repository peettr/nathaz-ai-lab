from pathlib import Path
import shutil,json
R=Path(__file__).parent;S=Path((R/'SOURCE_ROOT.txt').read_text().strip());t=(S/'controller_t18.py').read_text()
def c(a,b):
 global t
 assert t.count(a)==1,(a,t.count(a));t=t.replace(a,b)
c('RATE=5.4; CAP=13.1','RATE=5.4; CAP=6.5')
c("CASES=('K1a_s1','K1b_s1','K2_s1','K3a_s1','K3b_s1')","CASES=('K3a_s1','K3b_s1')")
c("if c0 not in verified or 'C0_K3a_solver.log' not in verified:return 'failed'","if c0 not in verified or 'C0_K3a_solver.log' not in verified or any(g+'_opencl_compilecheck.log' not in verified for g in ('K3a','K3b')):return 'failed'")
c("expected=list(CASES if smoke.get('pass') else CASES[:3])","expected=list(CASES if smoke.get('pass') else ())")
c("log('PRELAUNCH_TWO_CASE_MARGIN_S',margin)","log('PRELAUNCH_K3_TWO_CASE_MARGIN_S',margin)")
c("name='luw-t17b3-'+uuid.uuid4().hex[:9]","name='luw-t18k3-'+uuid.uuid4().hex[:9]")
(R/'controller_k3.py').write_text(t)
plan=json.loads((S/'SESSION_PLAN.json').read_text());plan.update({'full_chain_upper_CU':6.2,'full_chain_upper_s':4100,'first_case_upper_CU':2.1,'single_session_cap_CU':6.5,'reference':'K3 two cases only; absolute cap 6.5 CU, prelaunch 4100s margin. Estimated not billing.'});(R/'SESSION_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
# Stub remains clearly synthetic for local real-worker orchestration check only.
p=R/'stub_t18.py';v=p.read_text();v=v.replace("if os.environ.get('T17_B_MODE')=='smoke':","if os.environ.get('T17_B_MODE')=='compilecheck':\n d=Path(os.environ['T17_B_DIR']);d.mkdir(exist_ok=True);(d/'producer.done').write_text('10\\n');print('FIXTURE ONLY OpenCL C code successfully compiled')\nelif os.environ.get('T17_B_MODE')=='smoke':");p.write_text(v)
v=(S/'dry_check_t18_final.py').read_text();v=v.replace("'dry_content_t18_final'","'dry_content_k3'").replace("'DRY_WORKER_T18_final.log'","'DRY_WORKER_K3.log'").replace("'DRY_PASS_T18_v8.json'","'DRY_PASS_K3.json'").replace("('K1a','K1b','K2','K3a','K3b')","('K3a','K3b')").replace("13.1*3600/5.4","6.5*3600/5.4");(R/'dry_check_k3.py').write_text(v)
# Spool only payload/control files; existing records are immutable.
sp=Path.home()/'luw_tmp'/R.name;sp.mkdir(parents=True,exist_ok=False)
for n in ('controller_k3.py','worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','machine.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json'):
 shutil.copy2(R/n,sp/n)
(sp/'NATIVE_PRODUCER_APPROVED.ok').write_text('K3 worker actual native OpenCL 10-step checks before C0; local dry run required before launch.\n')
import hashlib
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(sp/'PREFLIGHT.ok').write_text(json.dumps({n:sha(sp/n) for n in ('controller_k3.py','worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','machine.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json')},indent=2)+'\n')
print('spool',sp)
