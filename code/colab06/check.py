import pathlib
p=pathlib.Path('/content/l264surface06')
for name in ('worker.log','stage.log','install.log','pilot.log','surface.log'):
 f=p/name
 if f.exists():print(name, f.stat().st_size, f.read_text(errors='replace')[-900:])
for name in ('stage.done','install_py310.done','pilot.json','budget_go','run.done','run.failed'):
 print(name,(p/name).exists())
