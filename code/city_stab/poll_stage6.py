from pathlib import Path
p=Path("/content/luw_stage6_noT_1016/progress.log")
print(p.read_text() if p.exists() else "no progress yet")
