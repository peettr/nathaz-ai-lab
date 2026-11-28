from pathlib import Path
import subprocess
p=Path('/content/setup_gc37_v3.log')
print(p.read_text()[-1600:] if p.exists() else 'NOT_STARTED')
print(subprocess.run(['pgrep','-af','setup_gc37_vm.py'],capture_output=True,text=True).stdout)
