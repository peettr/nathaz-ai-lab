from pathlib import Path
p=Path("/content/luw_stage6_noT_1016/solver.log")
t=p.read_text(errors="replace")
print(len(t))
print(t[-3000:])