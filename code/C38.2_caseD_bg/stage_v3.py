"""Stage immutable v3 attempts in fresh roots; no Colab side effect."""
from pathlib import Path
import shutil,re,datetime,hashlib,json
ROOT=Path(__file__).resolve().parent
CASES={
 'CaseD':('CaseD_retry9_20261115_0756','cased_stage.tar.gz','remote_caseD.py','caseD_result.zip',5.0),
 'BG_1H':('BG_1H_retry3_20261115_0906','bg_stage.tar.gz','remote_BG.py','BG_1H_result.zip',3.0),
 'BG_3H':('BG_3H_retry2_20261115_0915','bg_stage.tar.gz','remote_BG.py','BG_3H_result.zip',3.0),
}

def stage(case,tag):
    src,archive,worker,result,cap=CASES[case];S=ROOT/src;D=ROOT/f'{case}_v3_{tag}';D.mkdir(exist_ok=False)
    remote=f'/content/luw-c38-{case.lower().replace("_", "")}-v3-{tag}'
    session=f'luw-c38-{case.lower().replace("_", "")}-v3-{tag}'
    for name in ('controller.py','launch.py','check.py','gpu_probe.py','verify_source.py','verify_diagnostic_upload.py','diagnostic_extract.py',archive,worker):
        if (S/name).exists(): shutil.copy2(S/name,D/name)
    shutil.copy2(ROOT/'v3_alignment.py',D/'v3_alignment.py')
    old_remote=re.search(r"R=pathlib.Path\('([^']+)'\)", (S/worker).read_text()).group(1)
    w=(D/worker).read_text().replace(old_remote,remote)
    assert old_remote not in w
    assert '  gate()\n' in w and ' points()\n' in w
    w=w.replace('  gate()\n','  gate()\n  from v3_alignment import register\n  stl=next((gate_dir/"proj_temp").glob("*_PF.stl"))\n  register(stl,read_vtk,next((gate_dir/"RESULTS/vtk").glob("*_avg-*.vtk")),E,"'+case+'")\n',1)
    w=w.replace(' points()\n',' from v3_alignment import sample_points\n registration=json.loads((E/"iou_registration.json").read_text())\n dx,dy=registration["selected_offset_xy_m"]\n stl=next((C/"proj_temp").glob("*_PF.stl"))\n sample_points(stl,read_vtk,next((C/"RESULTS/vtk").glob("*_avg-*.vtk")),E,P/"'+('caseD' if case=='CaseD' else 'bg')+'_points.csv","'+case+'",dx,dy,sha)\n',1)
    w=w.replace("'pointvalues.json',*diagnostic_hashes","'pointvalues.json','iou_registration.json',*diagnostic_hashes")
    # build may have run before IoU; stop if IoU gate fails.
    (D/worker).write_text(w)
    launch=(D/'launch.py').read_text().replace(old_remote,remote);(D/'launch.py').write_text(launch)
    check=(D/'check.py').read_text().replace(old_remote,remote);(D/'check.py').write_text(check)
    c=(D/'controller.py').read_text();old_name=re.search(r"NAME='([^']+)'",c).group(1)
    c=c.replace(old_name,session).replace(old_remote,remote)
    c=c.replace('3.90/rate','2.90/rate' if case.startswith('BG') else '4.90/rate')
    c=c.replace("'geometry_gate.json','solver_exit.json','sha256.json'","'geometry_gate.json','iou_registration.json','solver_exit.json','sha256.json'")
    # Also ensure uploaded module is included and verified by remote hash before launching.
    old="(D/'diagnostic_extract.py','/content/diagnostic_extract.py')"
    assert old in c
    c=c.replace(old,old+",(D/'v3_alignment.py','/content/v3_alignment.py')")
    c=c.replace("assert 'DIAGNOSTIC_SHA256 '+localsha(D/'diagnostic_extract.py') in check_diag,check_diag[-600:]","assert 'DIAGNOSTIC_SHA256 '+localsha(D/'diagnostic_extract.py') in check_diag,check_diag[-600:]")
    # remote verify source script checks module separately in worker
    w=(D/worker).read_text();needle=" manifest=json.loads((P/'manifest.json').read_text())"
    assert needle in w
    w=w.replace(needle," assert sha('/content/v3_alignment.py')=='"+hashlib.sha256((D/'v3_alignment.py').read_bytes()).hexdigest()+"'\n"+needle);(D/worker).write_text(w)
    # A bounded result export and budget guard are kept intact.
    c=c.replace('f\'5 CU predicted exceedance:',f"f'{cap:g} CU predicted exceedance:").replace('f\'4 CU predicted exceedance:',f"f'{cap:g} CU predicted exceedance:")
    (D/'controller.py').write_text(c)
    (D/'RUN_PLAN.json').write_text(json.dumps({'case':case,'source_run_root':str(S),'new_run_root':str(D),'session':session,'budget_CU':cap,'source_archive_sha256':hashlib.sha256((S/archive).read_bytes()).hexdigest(),'worker_sha256':hashlib.sha256((D/worker).read_bytes()).hexdigest(),'aligner_sha256':hashlib.sha256((D/'v3_alignment.py').read_bytes()).hexdigest(),'conditions':'IoU independent of point errors; native geometry and per-building gate before solve; same source/config; compare VTK SHA; session CU includes startup and all attempts'},indent=2))
    print(D)
if __name__=='__main__':
    import sys
    assert len(sys.argv)==3
    stage(*sys.argv[1:])
