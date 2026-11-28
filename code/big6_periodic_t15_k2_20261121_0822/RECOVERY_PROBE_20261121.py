import json, pathlib, subprocess
c=pathlib.Path('/content')
paths=['remote_B.py','t17b.launch','t17b.log','t17b/out/run.done','t17b/out/run.failed','t17b/out/t15_s1_case.json','t17b/out/t15_s2_case.json']
print('T17_RECOVERY '+json.dumps({'paths':{n:(c/n).exists() for n in paths},'out_names':sorted(p.name for p in (c/'t17b/out').iterdir()) if (c/'t17b/out').exists() else [],'process':subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout[-4000:]}),flush=True)
