"""Synthetic preflight only: test unmodified extraction/compare logic in isolated fixture."""
from pathlib import Path
import tempfile, subprocess, json, struct, shutil, sys
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='caseA_preflight_') as tmp:
 r=Path(tmp);(r/'caseA/RESULTS/vtk').mkdir(parents=True);(r/'solver.exit').write_text('exit=0\n')
 original=json.loads((root/'caseA_observations_official.json').read_text());p=next(iter(original['groups']['z8']))
 p=dict(p,x=2.,y=2.,z=2.,speed=0.6,k=0.1)
 p2=dict(p,x=3.,y=3.,speed=0.8,k=0.2)
 obs={'UH':original['UH'],'groups':{'z8':[p,p2],'z80':[p,p2],'vertical':[p,p2]}}
 (r/'caseA_observations_official.json').write_text(json.dumps(obs));shutil.copy2(root/'metrics_caseA_turb.json',r/'metrics_caseA_turb.json')
 N=4**3
 header=b'# vtk DataFile Version 3.0\nfixture\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 4 4 4\nORIGIN 0 0 0\nSPACING 2 2 2\nPOINT_DATA 64\nSCALARS u_avg float 3\nLOOKUP_TABLE default\n'
 with (r/'caseA/RESULTS/vtk/test_avg.vtk').open('wb') as f:
  f.write(header);f.write(struct.pack('>'+ 'f'*(N*3),*[v for q in range(N) for v in (1.+(q%4),2.,3.)]))
  for name in ('rho_avg','fluid','tke'):
   values=[1.+(q%4)*0.1 if name=='tke' else 1. for q in range(N)]
   f.write(f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode());f.write(struct.pack('>'+ 'f'*N,*values))
 source=(root/'extract_r9.py').read_text().replace('for z in (32.,62.,64.,66.):','for z in (2.,):').replace('range(322,384,2)','range(2,4,2)').replace("altz=8. if key=='z8' else 80.","altz=2.").replace("((100.,100.),(320.,320.))","((2.,2.),(2.,2.))")
 (r/'extract_r9.py').write_text(source);shutil.copy2(root/'compare_r9.py',r/'compare_r9.py')
 for name in ('extract_r9.py','compare_r9.py'):
  proc=subprocess.run([sys.executable,str(r/name)],cwd=r,text=True,capture_output=True)
  print(name,proc.returncode,proc.stdout[-400:],proc.stderr[-600:]);assert proc.returncode==0
 sample=json.loads((r/'samples_caseA_r9_2m.json').read_text());assert sample['dimensions']==[4,4,4] and sample['spacing']==2.0
 assert all(len(v)==2 for v in sample['groups'].values());assert all(len(v)==2 for v in sample['diagnostic'].values())
 assert (r/'metrics_caseA_r9_2m.json').is_file()
print('PREFLIGHT_SYNTHETIC_OK (not a scientific result)')
