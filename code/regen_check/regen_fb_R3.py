"""只读核验：用 collect 脚本同一 excerpt 规则，从 CRC 运行根重新生成两份被删的 fb_R3.txt，写到本目录，不写回原目录。"""
import subprocess,hashlib
HOST='[邮箱]'
OPT=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
for i,root in [('T03_N_r1','/groups/kareem/[用户]/L22_6/L22_6_R3_claude_T03_N_r1_20261105'),('T03_W_r1','/groups/kareem/[用户]/L22_6/L22_6_R3_claude_T03_W_r1_20261105_b')]:
    raw=subprocess.run(['ssh','-n',*OPT,HOST,f'cat {root}/solver_work/compile.log'],capture_output=True,text=True,timeout=45).stdout
    t='\n'.join(raw.splitlines()[:200]).rstrip('\n')+'\n'
    p=f'regen_check/claude_{i}_fb_R3.txt'; open(p,'w').write(t)
    b=open(f'claude/{i}/fb_R2.txt').read()
    print(i,len(t),hashlib.sha256(t.encode()).hexdigest()[:16],'same_as_fb_R2=',t==b)
