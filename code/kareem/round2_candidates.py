#!/usr/bin/env python3
"""Read-only page-aware local PDF sentence browser; stdout only."""
import sys,re,subprocess
from pathlib import Path
from inspect_papers import P,R
ST=Path('./.hermes/profiles/researchos-literature/Kareem12_PDF_Staging')
EX={'04':ST/'04_Shape.pdf','05':ST/'05_Article.pdf','06':ST/'06_PeakFactors.pdf','07':ST/'07_Article.pdf','08':ST/'08_Article.pdf','09':ST/'09_Article.pdf','10':ST/'10_Article.pdf','11':ST/'11_POD.pdf','12':ST/'12_VIV.pdf'}
CUE=re.compile(r'\b(should|must|however|necessary|important|cannot|need|limited|limit|lack|problem|difficult|inadequate|uncertain|challenge|critical|rather than|unlike|assumption|in contrast|not always|not only|not suitable|overestimat|underestimat|therefore|recommended|requires?|neglect|fail|fundamental|consequently|in practice)\b',re.I)
SELF=re.compile(r'^(This (study|paper|work|research|approach|method|model)|In this (study|paper|work)|We (propose|present|develop|introduce|show)|Our (results|method|model))\b',re.I)
def pages(id):
 path=str(EX[id] if id in EX else P[id][0])
 t=subprocess.run(['pdftotext','-raw',path,'-'],capture_output=True,text=True,check=True).stdout
 return [x for x in t.split('\f') if x.strip()]
def sentences(text):
 text=re.sub(r'(?<=\w)-\s*\n(?=\w)','',text)
 text=re.sub(r'\s+',' ',text).strip()
 return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(“\[0-9])',text) if len(s.strip())>55]
if __name__=='__main__':
 for id in sys.argv[1].split(','):
  pp=pages(id);print('\n###',id,R[id]['title'] if id in R else EX[id].name,'PAGES',len(pp))
  for n,p in enumerate(pp,1):
   if n==1:continue
   ss=[s for s in sentences(p) if CUE.search(s) and not SELF.search(s) and len(s)<500]
   # Allow by page, optionally cap; no bibliography pages with excessive year/doi numbers
   print('PAGE',n,' '.join(f'[{i}] {s[:270]}' for i,s in enumerate(ss[:int(sys.argv[2]) if len(sys.argv)>2 else 5],1)))
