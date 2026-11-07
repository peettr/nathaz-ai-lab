from pathlib import Path
import hashlib,json
r=Path('/content/luw-aij-caseA-turb-20261014')
print(json.dumps({n:{'sha256':hashlib.sha256((r/n).read_bytes()).hexdigest(),'size':(r/n).stat().st_size} for n in ['solver.log','solver.metrics','solver.exit','solver_wrapper.log']},indent=2))
