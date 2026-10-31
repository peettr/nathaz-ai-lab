from pathlib import Path
import subprocess
p=Path('/content')
for f in sorted(p.glob('a_v3*')): print(f.name,f.stat().st_size, f.read_text()[-1500:] if f.suffix in ('.log','.exit') else '',flush=True)
print(subprocess.run(['pgrep','-af','chain_a_v3.py'],capture_output=True,text=True).stdout)
