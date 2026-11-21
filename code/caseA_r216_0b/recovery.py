from pathlib import Path
import sys,json,time
sys.path.insert(0,'/content');import recover_remote as a
r=Path('/content/r216_caseA_0b');p=a.extract(r/'r9_dx10','r9_dx10',10.);print('RECOVERED',p,p.stat().st_size,a.digest(p));old=json.loads((r/'out/evidence_r9_dx4.json').read_text());print('R9_4',old['exit'],old['samples_size']);(r/'out/evidence_r9_dx10_recovered.json').write_text(json.dumps({'exit':0,'steps_requested':6400,'samples':str(p),'samples_sha256':a.digest(p),'vtk_size':next((r/'r9_dx10').glob('RESULTS/vtk/*_avg*.vtk')).stat().st_size},indent=2));(r/'done').write_text(str(time.time()))
