import pathlib, runpy, os, datetime
r=pathlib.Path("/content/s2")
r.mkdir(exist_ok=True)
marker=r/"vm2_1027.launch"
with marker.open("x") as f:
 f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+"\n")
runpy.run_path("/content/s2_resume_launch_1022.py",run_name="__main__")
