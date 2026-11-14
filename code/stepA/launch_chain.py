import subprocess
subprocess.Popen("nohup python /content/l2612-stepA/chain_l2612.py > /content/l2612-stepA/chain.out 2>&1 &", shell=True, cwd="/content/l2612-stepA")
print("chain launched", flush=True)
