import subprocess, pathlib
print(subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],text=True))
print('lock',pathlib.Path('/content/try13.launch.lock').exists(),'done',pathlib.Path('/content/try13.done').exists())
