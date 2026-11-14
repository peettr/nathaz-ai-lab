import glob,hashlib,tarfile,os,subprocess,sys,time,json,traceback
from pathlib import Path
root=Path('/content');log=root/'stage.log';status=root/'stage_status.json'
try:
 ps=sorted(glob.glob('/content/inputs.part.*'));assert len(ps)==6
 h=hashlib.sha256()
 with open(root/'data_archive.tar','xb') as dst:
  for p in ps:
   with open(p,'rb') as src:
    for b in iter(lambda:src.read(1024*1024),b''):dst.write(b);h.update(b)
 assert h.hexdigest()=='8f3d141b48d02e8f9d3cc4bbcc45aba84295befc6d803616fd29a933c045133c'
 with tarfile.open(root/'data_archive.tar') as tar:
  for m in tar.getmembers():
   assert m.name==os.path.basename(m.name) and m.isfile(),m.name
  tar.extractall('/content/data',filter='data')
 print('archive verified, files',len(list((root/'data').iterdir())),flush=True)
 # Existing model wheel pinned and security checked in prior L26.15; captum inspected locally.
 cmd=[sys.executable,'-m','pip','install','-q','--extra-index-url','https://pypi.nvidia.com','/content/nvidia_physicsnemo-2.2.2-py3-none-any.whl','/content/captum-0.8.0-py3-none-any.whl']
 z=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1200)
 print('pip status',z.returncode,z.stdout[-3000:],flush=True);assert z.returncode==0
 import importlib.metadata as mt
 print('installed',mt.version('nvidia-physicsnemo'),mt.version('captum'),flush=True)
 status.write_text(json.dumps({'ok':True,'archive_sha256':h.hexdigest(),'files':len(list((root/'data').iterdir()))}))
except Exception as e:
 traceback.print_exc();status.write_text(json.dumps({'ok':False,'error':str(e)}))
 raise
