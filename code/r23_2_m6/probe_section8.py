from pathlib import Path
import os
p=Path('/content/m6')
for name in ('section8_fit.log','section8_fit.exit','section8_fit.done','hold.log'):
 f=p/name
 print(name, f.exists(), f.stat().st_size if f.exists() else None, (f.read_text()[-600:] if f.exists() and f.stat().st_size<30000 else ''))
for pid in (172851,174273):
 try: print('pid',pid,(Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ')[:200])
 except Exception as e: print('pid',pid,e)
