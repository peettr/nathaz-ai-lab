from pathlib import Path
r=Path(__file__).parent
s=(r/'compare_caseA_turb.py').read_text()
s=s.replace("r=Path(__file__).parent", "r=Path('/content/luw-aij-caseA-turb-20261014')")
(r/'compare_caseA_turb_remote.py').write_text(s)
