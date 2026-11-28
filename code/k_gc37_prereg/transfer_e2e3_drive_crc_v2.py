#!/usr/bin/env python3
"""Stream immutable Drive forecast artifacts through existing CRC mux; verify SHA256 and MD5."""
import hashlib, json, os, pathlib, shlex, subprocess, sys
SRC='gdfull:colab_cache/r234c_e2e3_forecasts_20261115_v1'
ROOT='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37'
HOST='[邮箱]'
SOCK='./.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=20',HOST]
CYCLES={'E2':{'2024051818':5,'2024051718':9,'2024051618':13},'E3':{'2024071218':6,'2024071118':10,'2024071018':14}}
def run(cmd,**kw):
    kw.setdefault('check', True)
    return subprocess.run(cmd,**kw)
def remote(cmd):
    return run(SSH+[cmd],capture_output=True,text=True,timeout=180).stdout

def main():
    assert pathlib.Path(SOCK).is_socket()
    assert 'Master running' in run(['ssh','-O','check','-o',f'ControlPath={SOCK}',HOST],capture_output=True,text=True,timeout=20).stderr
    assert 'OK' in remote('echo OK')
    for event,cycles in CYCLES.items():
        root=f'{ROOT}/gc37_raw_{event}_v1'
        remote('mkdir -p '+shlex.quote(root))
        for cycle,steps in cycles.items():
            dest=f'{root}/{cycle}'
            remote('mkdir -p '+shlex.quote(dest))
            source=f'{SRC}/{cycle}'
            manifest=json.loads(run(['rclone','cat',source+'/RAW_MANIFEST.json'],capture_output=True).stdout)
            assert len(manifest)==steps and [x['file'] for x in manifest]==[f'step_{i:02d}.npz' for i in range(1,steps+1)]
            sums=[]
            for item in manifest:
                name=item['file'];target=dest+'/'+name
                expected=item['sha256'];size=item['bytes']
                assert len(expected)==64 and size>0
                exists=remote('if test -e '+shlex.quote(target)+'; then sha256sum '+shlex.quote(target)+'; fi').strip()
                if exists:
                    assert exists.split()[0]==expected,(target,'existing mismatch',exists)
                else:
                    partial=target+'.partial'
                    assert not remote('if test -e '+shlex.quote(partial)+'; then echo PRESENT; fi').strip(),partial
                    reader=subprocess.Popen(['rclone','cat',source+'/'+name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    try:
                        writer=subprocess.run(SSH+['umask 027; cat > '+shlex.quote(partial)],stdin=reader.stdout,capture_output=True,timeout=600)
                    finally:
                        reader.stdout.close()
                    err=reader.communicate(timeout=60)[1]
                    if reader.returncode or writer.returncode:
                        raise RuntimeError((cycle,name,reader.returncode,writer.returncode,err[-500:],writer.stderr[-500:]))
                    result=remote('stat -c %s '+shlex.quote(partial)+'; sha256sum '+shlex.quote(partial)).splitlines()
                    assert int(result[0])==size and result[1].split()[0]==expected,(target,result)
                    remote('mv -n '+shlex.quote(partial)+' '+shlex.quote(target))
                sums.append(expected+'  '+name)
                print('TRANSFER_OK',event,cycle,name,size,flush=True)
            sums_text='\n'.join(sums)+'\n'
            for name,content in [('SHA256SUMS',sums_text),('RAW_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')]:
                target=dest+'/'+name
                existing=remote('if test -e '+shlex.quote(target)+'; then sha256sum '+shlex.quote(target)+'; fi').strip()
                digest=hashlib.sha256(content.encode()).hexdigest()
                if existing: assert existing.split()[0]==digest,(target,existing,digest)
                else:
                    run(SSH+['umask 027; cat > '+shlex.quote(target)],input=content,text=True,capture_output=True,timeout=90)
            checked=remote('cd '+shlex.quote(dest)+' && sha256sum -c SHA256SUMS')
            assert checked.count(': OK')==steps,(cycle,checked)
            print('CYCLE_VERIFIED',event,cycle,steps,flush=True)
    print('ALL_RAW_VERIFIED',flush=True)
if __name__=='__main__':main()
