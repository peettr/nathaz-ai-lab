#!/usr/bin/env python3
"""Colab A100 only. Native gate, one full round-9 run per Case C variant."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import traceback
import zipfile
from extract_caseC import Field, gate, register, extract, sha
from patch_scalar_mean import patch

R=Path(os.environ['CASEC_REMOTE_ROOT'])
P=R/'payload';E=R/'evidence';CASES=('0D','1D','2D')
R.mkdir(parents=True,exist_ok=True);E.mkdir(exist_ok=True)


def log(event,**kw):
    with (R/'run.log').open('a') as f:
        f.write(json.dumps({'when':time.time(),'event':event,**kw})+'\n');f.flush()


def run_cmd(cmd,cwd,out):
    log('command',cmd=cmd,cwd=str(cwd))
    with (R/out).open('a') as f:
        result=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    log('command_exit',cmd=cmd,rc=result.returncode)
    assert result.returncode==0,(cmd,result.returncode,R/out)


def solve(binary,case_root,label,deadline):
    assert time.time()+150<deadline,'insufficient reserve before solve'
    with (R/f'{label}_solver.log').open('x') as f:
        p=subprocess.Popen([str(binary),str(case_root/'conf.luwpf')],cwd=case_root,
                           stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        log('solver_started',case=label,pid=p.pid)
        try: rc=p.wait(timeout=max(1,deadline-time.time()-130))
        except subprocess.TimeoutExpired:
            p.terminate()
            try: p.wait(timeout=20)
            except subprocess.TimeoutExpired: p.kill();p.wait()
            log('budget_stop',case=label,rc=p.returncode)
            raise RuntimeError('solver reached CU stop reserve')
    log('solver_exit',case=label,rc=rc)
    assert rc==0,(label,rc)
    vtk=list((case_root/'RESULTS/vtk').glob('*_avg-*.vtk'))
    assert len(vtk)==1,(label,vtk)
    return vtk[0]


def modified_deck(base,steps,avg_start,avg_stride):
    text=base.read_text()
    for key,value in (('run_nstep',steps),('purge_avg',avg_start),('purge_avg_stride',avg_stride)):
        match=list(re.finditer(r'(?m)^'+key+r' = (\d+)$',text));assert len(match)==1,(key,len(match))
        text=text[:match[0].start(1)]+str(value)+text[match[0].end(1):]
    return text


def stage_case(label,manifest):
    src=P/f'caseC_{label}.tar.gz'
    assert sha(src)==manifest['cases'][label]['tar_sha256']
    with tarfile.open(src) as t:
        names=[x.name for x in t]
        assert all(x.startswith('caseC_'+label+'/') and '..' not in Path(x).parts for x in names)
        assert all(x.isfile() or x.isdir() for x in t)
        t.extractall(R/'cases',filter='data')
    case=R/'cases'/f'caseC_{label}'; info=manifest['cases'][label]
    for relative,key in [('conf.luwpf','deck_sha256'),('wind_bc/profile.dat','profile_sha256'),
                         (f'proj_temp/caseC_{label}_PF.stl','stl_sha256')]:
        assert sha(case/relative)==info[key],(relative,key)
    assert sha(P/f'caseC_{label}_points.csv')==info['points_sha256']
    return case


def main():
    assert not (R/'started').exists();(R/'started').touch(exist_ok=False)
    deadline=float((R/'deadline_epoch').read_text());manifest=json.loads((P/'STAGING.json').read_text())
    assert manifest['grid']==[250,150,75] and manifest['dx_m']==2
    for label in CASES: stage_case(label,manifest)
    source=R/'source'; source.mkdir(exist_ok=False)
    archive=R/'source_dd438c1.tar.gz'
    with archive.open('xb') as out:
        for part in sorted(P.glob('part_*')):
            with part.open('rb') as f:shutil.copyfileobj(f,out)
    assert sha(archive)=='88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
    with tarfile.open(archive) as t:t.extractall(source,filter='data')
    original=json.loads((P/'source_hashes.json').read_text())
    assert len(original)>100
    for name,h in original.items():assert sha(source/name)==h,name
    setup=source/'core/cfd_core/FluidX3D/src/setup.cpp'
    assert sha(setup)=='d5641072b1e4c3b9ea3ed85a0109b850e7022c90ff30e8844dd80edbb4ed7829'
    setup.write_text(patch(setup.read_text()))
    assert sha(setup)=='baa3531a248d1b21ae97f1cca39ab1b950983614943af1a26e706c0fc4903262'
    if os.environ.get('CASEC_STUB')=='1':
        for label in CASES:
            case=R/'cases'/f'caseC_{label}'
            run_cmd(['python3',str(P/'stub_solver.py'),str(case/'conf.luwpf')],case,f'{label}_stub_solver.log')
            log('STUB_ACK',case=label,deck=str(case/'conf.luwpf'),
                profile=str(case/'wind_bc/profile.dat'),stl=str(case/'proj_temp'/f'caseC_{label}_PF.stl'))
        (R/'stub.done').write_text('STUB_ONLY_NO_PHYSICAL_FIELDS\n')
        return
    run_cmd(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],R,'gpu.log')
    assert 'A100' in (R/'gpu.log').read_text()
    run_cmd(['make','Linux','-j2'],source/'core/cfd_core/FluidX3D','build.log')
    binary=source/'core/cfd_core/FluidX3D/bin/FluidX3D';assert binary.is_file()
    for label in CASES:
        case=R/'cases'/f'caseC_{label}'
        # Gate and 1000-step calibration are distinct roots; no output overwritten.
        for typ,steps in [('gate',1),('calibration',1000)]:
            sub=R/(label+'_'+typ);shutil.copytree(case,sub,ignore=shutil.ignore_patterns('RESULTS'))
            (sub/'conf.luwpf').write_text(modified_deck(sub/'conf.luwpf',steps,1,1))
            start=time.monotonic();vtk=solve(binary,sub,label+'_'+typ,deadline)
            if typ=='gate':
                field=Field(vtk)
                try:
                    geometry=gate(field,label)
                    registration=register(field,case/'proj_temp'/f'caseC_{label}_PF.stl',label)
                finally:field.close()
                (E/f'{label}_geometry_gate.json').write_text(json.dumps({'gate':geometry,'registration':registration},indent=2))
                log('GEOMETRY_GATE_PASS',case=label,gate=geometry,registration=registration)
            else:
                elapsed=time.monotonic()-start
                (E/f'{label}_calibration.json').write_text(json.dumps({'steps':1000,'wall_seconds':elapsed}))
                log('calibration',case=label,wall_seconds=elapsed)
                # Complete remaining cases, conservative 2x rate + fixed export/stop reserve.
                pending=CASES[CASES.index(label):]
                assert time.time()+2*elapsed*14487/1000*len(pending)+180<deadline, ('insufficient budget',label,elapsed,pending)
        vtk=solve(binary,case,label,deadline)
        output=E/(label+'_points'); data=extract(label,vtk,P/f'caseC_{label}_points.csv',
                                                 case/'proj_temp'/f'caseC_{label}_PF.stl',output)
        # Solver terminal step and actual sample count are read from its own log, not assumed.
        solverlog=(R/f'{label}_solver.log').read_text(errors='replace')
        (output/'solver_log_tail.txt').write_text(solverlog[-16000:])
        with zipfile.ZipFile(E/f'{label}_result.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
            for item in [output/f'caseC_{label}_pointvalues.csv',output/'extraction.json',
                         output/'solver_log_tail.txt',E/f'{label}_geometry_gate.json',
                         E/f'{label}_calibration.json',R/f'{label}_solver.log',R/'build.log']:
                z.write(item,item.name)
        zfile=E/f'{label}_result.zip'
        ack={'case':label,'zip_sha256':sha(zfile),'csv_sha256':data['csv_sha256'],
             'points_sha256':data['points_sha256'],'point_count':data['point_count'],
             'clamped':data['clamped'],'mixed_solid':data['mixed_solid'],
             'vtk_sha256':data['vtk_sha256'],'solver_log_tail_sha256':sha(output/'solver_log_tail.txt')}
        (E/f'{label}.ack.json').write_text(json.dumps(ack,indent=2))
        log('CASE_COMPLETE',**ack)
    (R/'run.done').write_text('success\n')
    log('SUCCESS',cases=list(CASES))


if __name__=='__main__':
    try:main()
    except BaseException:
        log('FAILED',trace=traceback.format_exc())
        (R/'run.failed').write_text(traceback.format_exc())
        raise
