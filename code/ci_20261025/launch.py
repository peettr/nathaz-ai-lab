import hashlib, json, os, subprocess, tarfile, pathlib, sys
from pathlib import Path
base=Path('/content'); inp=base/'pairs'; inp.mkdir(exist_ok=True)
for net in ('OKC','Swiss'):
    with tarfile.open(base/f'{net}.tgz') as t:
        files=[m for m in t if m.name==f'pairs/{net}_GFS_test_delay4.parquet']
        assert len(files)==1
        with (inp/f'{net}_GFS_test_delay4.parquet').open('wb') as out:
            import shutil;shutil.copyfileobj(t.extractfile(files[0]),out)
assert hashlib.sha256((base/'m4_score_ci.py').read_bytes()).hexdigest()=='250cf064ffd5a1245367041460fe63554ee10b89c70a6fb47eea15aad2301f63'
log=(base/'ci.log').open('x')
cmd=[sys.executable,'/content/m4_score_ci.py','--pairs','/content/pairs','--original','/content','--config','/content/config.json','--out','/content/ci_result']
def shell():
    result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    log.flush();log.close()
    (base/'ci.exit').write_text(str(result.returncode))
    (base/'ci.done').write_text('done')
# subprocess wrapper needs the completion marker: use a tiny external -c script
wrapper="import subprocess,pathlib,sys; r=subprocess.run("+repr(cmd)+",stdout=open('/content/ci.log','w'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL);pathlib.Path('/content/ci.exit').write_text(str(r.returncode));pathlib.Path('/content/ci.done').write_text('done')"
log.close();(base/'ci.log').unlink()
p=subprocess.Popen([sys.executable,'-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(json.dumps({'pid':p.pid,'files':{n:(inp/n).stat().st_size for n in ('OKC_GFS_test_delay4.parquet','Swiss_GFS_test_delay4.parquet')}}))
