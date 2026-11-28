import subprocess, torch, shutil
print('GPU',torch.cuda.get_device_name(), 'VRAM_GB',round(torch.cuda.get_device_properties(0).total_memory/1e9,2))
print('SPACE_GB',round(shutil.disk_usage('/content').free/1e9,2))
print(subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],capture_output=True,text=True).stdout)
