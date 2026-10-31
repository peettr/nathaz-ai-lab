#!/usr/bin/env python3
"""Print local first-page abstract sentences for human annotation."""
import sys,subprocess,re
from inspect_papers import R,P
for id in sys.argv[1].split(','):
 if id not in P:continue
 text=subprocess.run(['pdftotext','-raw','-f','1','-l','1',P[id][0],'-'],capture_output=True,text=True).stdout
 text=re.sub(r'(?<=\w)-\s*\n(?=\w)','',text);text=re.sub(r'\s+',' ',text)
 x=re.split(r'\b(?:Abstract:|ABSTRACT:|Abstract|A B S T R A C T)\s*',text,maxsplit=1,flags=re.I)
 if len(x)==2:text=x[1]
 text=re.split(r'\b(?:Introduction|Keywords:|Author keywords:|DOI:|1\.\s+Introduction|© 20\d\d)\b',text,maxsplit=1)[0]
 print('\n###',id,R[id]['title'])
 for j,s in enumerate(re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)):
  if 35<len(s)<700: print(j,s)
