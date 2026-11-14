from pathlib import Path
import subprocess
p=Path('/content')
print((p/'run_v3_r2.sh').read_text())
print(subprocess.run(['ps','auxww'],capture_output=True,text=True).stdout[-6000:])
for f in sorted(p.glob('a_v3_r2*')):print(f.name,f.stat().st_size, f.read_text()[-500:] if f.suffix in ('.log','.exit') else '')
