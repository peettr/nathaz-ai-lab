#!/usr/bin/env python3
"""Independent hard stop for the one owned Colab CPU session, never another."""
import subprocess,datetime,json,pathlib,shutil
R=pathlib.Path('./23_AI_Weather/06_Logs/R23.2d/p2_gust')
SESSION='r232d-p1-1111'; CFG=R/'colab_p1_state.json'; CLI=shutil.which('colab') or './.local/bin/colab'
log=R/'cutoff_p1.log'
def call(args):
    p=subprocess.run([CLI,'--auth','oauth2','--config',str(CFG),*args],capture_output=True,text=True,timeout=150)
    with log.open('a') as f:f.write(json.dumps({'at':datetime.datetime.now().astimezone().isoformat(),'args':args,'exit':p.returncode,'out':p.stdout[-2500:],'err':p.stderr[-1000:]},ensure_ascii=False)+'\n')
    return p
with log.open('a') as f:f.write(json.dumps({'at':datetime.datetime.now().astimezone().isoformat(),'event':'cutoff_fired'})+'\n')
for remote,name in [('/content/p1/stage1_attempt2.log','stage1_cutoff.log'),('/content/p1/stations_p2_frozen.csv','stations_p2_cutoff.csv'),('/content/p1/freeze_manifest.json','freeze_manifest_cutoff.json'),('/content/p1/archive_availability.jsonl','archive_availability_cutoff.jsonl'),('/content/p1/forecast_progress.jsonl','forecast_progress_cutoff.jsonl'),('/content/p1/pairs_p2.csv','pairs_p2_cutoff.csv')]:
    p=R/name
    if not p.exists():
        try:call(['download','-s',SESSION,remote,str(p)])
        except Exception as e:
            with log.open('a') as f:f.write('DOWNLOAD_EXCEPTION '+repr(e)+'\n')
try:
    archive=R/'p1_cutoff_archive.zip'
    if not archive.exists():
        try:
            result=call(['exec','-s',SESSION,'--timeout','150','-f',str(R/'archive_p1_remote.py')])
            if result.returncode==0:
                pulled=call(['download','-s',SESSION,'/content/p1/p1_cutoff_archive.zip',str(archive)])
                if pulled.returncode==0 and archive.exists():
                    import zipfile,hashlib
                    with zipfile.ZipFile(archive) as z:
                        manifest=json.loads(z.read('checkpoint_archive_manifest.json'))
                        assert all(hashlib.sha256(z.read(name)).hexdigest()==meta['sha256'] for name,meta in manifest.items())
                    with log.open('a') as f:f.write(json.dumps({'event':'archive_verified','sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(manifest)})+'\n')
        except Exception as e:
            with log.open('a') as f:f.write('ARCHIVE_EXCEPTION '+repr(e)+'\n')
    call(['stop','-s',SESSION])
finally:call(['sessions'])
