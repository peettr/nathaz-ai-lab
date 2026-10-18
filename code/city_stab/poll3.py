from pathlib import Path
import time
p=Path("/content/luw_stage6_noT_r2_1016/progress.log")
print("mtime_age",int(time.time()-p.stat().st_mtime))
print(p.read_text()[-600:])