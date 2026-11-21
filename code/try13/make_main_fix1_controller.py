#!/usr/bin/env python3
"""Clone controller into a distinct ownership/session/output contract."""
from pathlib import Path
r=Path(__file__).resolve().parent
src=(r/'main_smoke/controller.py').read_text()
src=src.replace("NAME='luw-t4-try13-main-smoke-1116'", "NAME='luw-t4-try13-main-smoke-fix1-1116'")
src=src.replace("SRC/'try13_main_archive.json'","BASE/'try13_main_archive_fix1.json'")
src=src.replace("SRC/'try13_main_stage.tar.gz'","BASE/'try13_main_stage_fix1.tar.gz'")
src=src.replace("SRC/'main_stage/FluidX3D_on/src'","BASE/'stage_t4/FluidX3D_on/src'")
src=src.replace("SRC/'main_smoke_worker.py'","SRC/'main_smoke_worker.py'")
src=src.replace("SRC/'main_smoke_launch.py'","SRC/'main_smoke_launch_fix1.py'")
src=src.replace("'/content/try13_main_stage.tar.gz'","'/content/try13_main_stage.tar.gz'")
src=src.replace("'/content/try13_main_archive.json'","'/content/try13_main_archive.json'")
src=src.replace("'/content/try13_main_smoke_worker.py'","'/content/try13_main_smoke_worker.py'")
# The remote worker retains its unique /content path; the previous VM is stopped.
assert "BASE/'stage_t4/FluidX3D_on/src'" in src
assert "BASE/'try13_main_archive_fix1.json'" in src
assert "SRC/'main_smoke_launch_fix1.py'" in src
out=r/'main_smoke_fix1/controller.py'
assert not out.exists()
out.write_text(src)
launch=(r/'main_smoke_launch.py').read_text()
new=r/'main_smoke_launch_fix1.py'
assert not new.exists()
new.write_text(launch)
print(out)
