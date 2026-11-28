from pathlib import Path
r=Path('/content/r216_caseA_0b');p=list(r.glob('r9_dx10/RESULTS/vtk/*_avg*.vtk'));print('files',[(str(x),x.stat().st_size) for x in p]);print(p[0].open('rb').read(550).decode('ascii','replace') if p else 'none');print('session_start',Path('/content/r216_session_start').read_text())
