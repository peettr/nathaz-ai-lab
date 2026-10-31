#!/usr/bin/env python3
"""Read-only physical-page and exact-text location audit of every stance card."""
import csv,pathlib,re,subprocess,collections,json
root=pathlib.Path(__file__).resolve().parent
idx={r['archive_id']:r for r in csv.DictReader((root.parent/'archive_index/kareem_archive_index.csv').open(encoding='utf-8-sig'))}
def norm(s):
 s=re.sub(r'(?<=\w)-\s+(?=\w)','',s)
 s=re.sub(r'\s+([,.;:!?])',r'\1',s)
 return re.sub(r'\s+',' ',s).strip()
errors=[]; totals=collections.Counter(); pdfs={}
for card in sorted((root/'cards').glob('KA-*.md')):
 key=card.stem; r=idx[key]; path=pathlib.Path(r['local_pdf_path'].split(';')[0]);text=card.read_text(encoding='utf-8')
 if not path.is_file(): errors.append([key,'PDF absent',str(path)]);continue
 pages=pdfs.setdefault(str(path),subprocess.run(['pdftotext','-raw',str(path),'-'],capture_output=True,text=True,check=True).stdout.split('\f'))
 # Each blockquote must have a page number in its immediately preceding bullet, even in old cards.
 for line in text.splitlines():
  if re.search(r'PDF (?:物理)?第\s*\d+\s*页',line): last=int(re.search(r'PDF (?:物理)?第\s*(\d+)\s*页',line).group(1))
  if line.lstrip().startswith('> '):
   q=line.lstrip()[2:];totals['quotes']+=1
   if 'last' not in locals() or not (1<=last<=len(pages)) or norm(q) not in norm(pages[last-1]): errors.append([key,'page_or_quote',last if 'last' in locals() else None,q[:100]])
   else:totals['located']+=1
   # punctuation count excludes abbreviation decimals and initial letters; report ambiguous only, do not silently classify.
   if len(re.findall(r'[.!?](?:\s|$)',q))>1:errors.append([key,'more_than_one_sentence',last,q[:100]])
 if 'last' in locals():del last
 totals['cards']+=1
print(json.dumps({'cards':totals['cards'],'quotes':totals['quotes'],'located':totals['located'],'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
