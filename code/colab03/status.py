from pathlib import Path
p=Path('/content/l264a100')
for name in ('stage.log','stage.done','stage.failed','install_py310_recovery.log','install_py310.done','install_py310.failed','static_probe.log','static_probe_retry.log','texas/static_probe.done'):
 f=p/name
 print(name, f.exists(), f.stat().st_size if f.exists() else '-', f.read_text(errors='replace')[-700:] if f.exists() and f.stat().st_size<100000 else '')
