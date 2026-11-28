import sys,subprocess,re
from inspect_papers import R,P
for id in sys.argv[1].split(','):
 print('\n###',id,R[id]['title'])
 if id not in P:continue
 text=subprocess.run(['pdftotext','-raw',P[id][0],'-'],capture_output=True,text=True).stdout
 pages=[p for p in text.split('\f') if p.strip()]
 for n in [1,*range(max(2,len(pages)-3),len(pages)+1)]:
  p=pages[n-1];p=re.sub(r'(?<=\w)-\s*\n(?=\w)','',p);p=re.sub(r'\s+',' ',p)
  print('PAGE',n,p[:(2900 if n==1 else 2500)])
