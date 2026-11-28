import subprocess
from pathlib import Path
p=subprocess.run(['python','-m','unittest','-v','test_rmw_adapter_v3'],cwd='/content',capture_output=True,text=True,timeout=150)
Path('/content/rmw_test_v3.log').write_text(p.stdout+p.stderr)
Path('/content/rmw_test_v3.exit').write_text(str(p.returncode))
print('exit',p.returncode,'\n',p.stdout,p.stderr)
