from pathlib import Path
import os,sys,importlib.util,json,hashlib
R=Path(__file__).resolve().parent
os.environ['T17_ARCHIVE_ROOT']=str(R)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ctrl=load('t18_ctrl_preflight',R/'controller_t18.py')
assert ctrl.CASES==('K1a_s1','K1b_s1','K2_s1','K3a_s1','K3b_s1')
rc,msg=ctrl.cmd([sys.executable,'-c','import time;time.sleep(2)'],timeout=.1)
assert rc==124 and msg.startswith('AMBIGUOUS_TIMEOUT')
probe_line='T17_PROBE '+json.dumps({'C0_verdict.json':{'sha':'abc','size':23}})
assert json.loads([line[len('T17_PROBE '):] for line in probe_line.splitlines() if line.startswith('T17_PROBE ')][0])['C0_verdict.json']['size']==23
remote=load('t18_remote_preflight',R/'remote_B.py')
c=R/'controller_fixture';c.mkdir(exist_ok=False);o=c/'t17b/out';o.mkdir(parents=True)
f=o/'C0_verdict.json';f.write_text('{"pass": false}\n');h=hashlib.sha256(f.read_bytes()).hexdigest();(o/(f.name+'.sha256')).write_text(h+'\n')
assert remote.probe(c)[f.name]=={'sha':h,'size':f.stat().st_size}
a={'K1a_s1_case.json':'abc'};(c/'K1a_s1.ack.pending').write_text(json.dumps(a));remote.ack(c,'K1a_s1')
assert json.loads((o/'K1a_s1.ack.json').read_text())==a
(R/'CONTROLLER_OFFLINE_TEST.json').write_text(json.dumps({'ambiguous_probe_timeout':'no stop action; returned 124','tagged_probe':'parsed nonempty JSON','ACK':'exact file moved to expected worker out','gpu_allocations':0},indent=2)+'\n')
print('CONTROLLER_OFFLINE_TEST_OK')
