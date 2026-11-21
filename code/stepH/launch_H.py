import subprocess,os
os.makedirs('/content/l2612-stepH',exist_ok=True)
subprocess.Popen("nohup python /content/l2612-stepH/chain_H.py > /content/l2612-stepH/chain.out 2>&1 &",shell=True)
print("launched",flush=True)
