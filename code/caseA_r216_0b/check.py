from pathlib import Path
import time,subprocess
r=Path('/content/r216_caseA_0b');print('now',time.time(),'session_elapsed',time.time()-float(Path('/content/r216_session_start').read_text()));print('done', (r/'done').exists(),'failed',(r/'failed').exists());print((r/'run.log').read_text()[-3000:] if (r/'run.log').exists() else 'no log');print('outputs',[(p.name,p.stat().st_size) for p in sorted((r/'out').glob('*'))]);print('process',subprocess.run(['pgrep','-af','run_remote.py'],capture_output=True,text=True).stdout[:500]);
