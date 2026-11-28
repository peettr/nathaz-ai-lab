import subprocess,sys,re
pdf=sys.argv[1]; pats=sys.argv[2:]
n=int(re.search(r'Pages:\s+(\d+)',subprocess.run(['pdfinfo',pdf],capture_output=True,text=True).stdout).group(1))
for i in range(1,n+1):
    t=' '.join(subprocess.run(['pdftotext','-f',str(i),'-l',str(i),pdf,'-'],capture_output=True,text=True).stdout.split())
    for p in pats:
        m=re.search(p,t,re.I)
        if m: print(f"p{i} [{p}]: ...{t[max(0,m.start()-220):m.end()+220]}...")
