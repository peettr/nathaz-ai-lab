#!/usr/bin/env python3.10
"""No GPU: exact probe/ACK scripts and controller verifier with fake worker files."""
import ast,contextlib,hashlib,io,json,os,pathlib,runpy,shutil,tempfile
import numpy as np
import controller
R=pathlib.Path(__file__).resolve().parent
source=(R/'worker.py').read_text()
assert "(O/'points80.json.sha256').write_text" in source
assert "(O/'upstream_slice.npz.sha256').write_text" in source
assert '(5,30,45)' in source
real=pathlib.Path
with tempfile.TemporaryDirectory(prefix='t8-handoff-',dir=os.environ.get('TMPDIR')) as td:
 root=real(td);remote=root/'remote';local=root/'download';remote.mkdir();local.mkdir()
 p=remote/'points80.json';p.write_text(json.dumps({'label':'E_s101_off','rows':[{'id':i} for i in range(1,81)]})+'\n')
 np.savez_compressed(remote/'upstream_slice.npz',tke=np.ones((62,201,61),dtype='f4'),u_avg=np.ones((62,201,61,3),dtype='f4'),fluid=np.ones((62,201,61),dtype='u1'))
 for name in ('points80.json','upstream_slice.npz'):
  (remote/(name+'.sha256')).write_text(hashlib.sha256((remote/name).read_bytes()).hexdigest()+'\n')
 class RemappedPath(type(real())):
  def __new__(cls,*args,**kw):
   if args and str(args[0])=='/content/t8_out':args=(str(remote),)+args[1:]
   if args and str(args[0])=='/content/t8.log':args=(str(root/'t8.log'),)+args[1:]
   return super().__new__(cls,*args,**kw)
 # Run scripts unchanged, with pathlib.Path mapped to the local fake VM path.
 old=pathlib.Path;pathlib.Path=RemappedPath
 try:
  out=io.StringIO()
  with contextlib.redirect_stdout(out):runpy.run_path(str(R/'probe.py'),run_name='__main__')
  payload=json.loads(out.getvalue().split('PROBE ',1)[1]);assert set(payload['ready'])=={'points80.json.sha256','upstream_slice.npz.sha256'}
  print('READY',sorted(payload['ready']))
  controller.O=local;controller.EVENT=root/'events.jsonl'
  def fake_pull(path,name,required=True):
   dest=local/name
   if not dest.exists():shutil.copyfile(remote/name,dest)
   return dest
  def fake_remote(script,env=None,timeout=110):
   if script=='ack.py':
    oldpair=os.environ.get('T8_PAIR');os.environ['T8_PAIR']=env['T8_PAIR'];buf=io.StringIO()
    try:
     with contextlib.redirect_stdout(buf):runpy.run_path(str(R/'ack.py'),run_name='__main__')
    finally:
     if oldpair is None:os.environ.pop('T8_PAIR',None)
     else:os.environ['T8_PAIR']=oldpair
    return buf.getvalue()
   raise AssertionError(script)
  controller.pull=fake_pull;controller.remote=fake_remote
  same,hashes=controller.verify_and_ack(payload)
  assert not same and len(hashes)==2
  assert (remote/'host.ack').read_text().strip()==' '.join(hashes)
  assert all((local/name).read_bytes()==(remote/name).read_bytes() for name in ('points80.json','upstream_slice.npz'))
  print('DOWNLOAD SHA256 VERIFIED',hashes)
  print('ACK RECEIVED', (remote/'host.ack').read_text().strip())
  print('DRY_HANDOFF_PASS (fake bytes intentionally differ from production baseline)')
 finally:pathlib.Path=old
