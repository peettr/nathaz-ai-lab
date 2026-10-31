import json, sqlite3, subprocess, re
from pathlib import Path
ROOT=Path('./');OUT=Path(__file__).parent
con=sqlite3.connect('file:./Zotero/zotero.sqlite?immutable=1',uri=True)
# Each fact is anchored in the source's Quantitative anchors; PDF pages checked programmatically.
FACTS={
'9CBNZGZB':[
('What is the building height H of the high-rise model in mm?','400','mm','400 mm'),
('What is the model building width B in mm?','133.33','mm','133.33'),
('How many surface faces per wind direction are in the RANS lattice?','7153','faces','7,153'),
('How many million cells approximately are in the LES mesh?','27','million cells','27 million')],
'AW3BMZ6P':[
('How many pressure taps in total?','1449','taps','1,449'),
('What air density is used?','1.225','kg/m3','1.225'),
('How many seconds are recorded after burn-in?','100','s','100 s'),
('What is the coarse-mesh CPU cost?','3360','CPU h','3,360')],
'FG72MNN8':[
('How many pressure taps in total?','252','taps','252'),
('What is the full-scale model scale ratio denominator?','400','1:denominator','400'),
('How many wind directions were evaluated?','72','directions','72'),
('How many interfering positions are considered?','37','positions','37')],
'L3RKLLUC':[
('How many configurations/conditions are in the database?','8568','conditions','8,568'),
('How many pressure taps?','252','taps','252'),
('How many height layers of taps?','9','layers','9')],
'LLMUL7GY':[
('What is the wind tunnel model building height H?','0.3','m','0.3'),
('How many taps are there?','360','taps','360'),
('What is the inlet nominal transverse intensity Iv/Iu?','0.5','1','0.5'),
('What is the nominal vertical intensity Iw/Iu?','0.8','1','0.8')],
'NF6S3H9N':[
('What is the reference wind speed Uref?','7.8','m/s','7.8'),
('What is the HF LES mesh size in millions of cells?','3.30','million cells','3.30'),
('What is the HF time step?','0.0003','s','0.0003')],
'SDI6BHAF':[
('What is the number of grid cells in millions?','23.6','million cells','23.6'),
('What is the maximum Mach number approximately?','0.06','1','0.06'),
('How long is the simulation statistics duration?','120','s','120')]
}
def pdf_for(key):
 rec=con.execute('select i.key,a.path from itemAttachments a join items i on i.itemID=a.itemID join items p on p.itemID=a.parentItemID where p.key=? and a.path like "%.pdf"',(key,)).fetchone()
 assert rec,key
 path=Path('./Zotero/storage')/rec[0]/rec[1].removeprefix('storage:')
 assert path.exists(),path
 return path
PAGE_HINT={'9CBNZGZB':[(2,3),(2,3),(9,9),(4,5)],'AW3BMZ6P':[(3,3),(3,3),(3,3),(4,4)],'FG72MNN8':[(5,5),(5,5),(5,5),(5,5)],'L3RKLLUC':[(8,9),(8,9),(8,9)],'LLMUL7GY':[(3,3),(3,3),(5,5),(5,5)],'NF6S3H9N':[(2,3),(2,3),(2,3)],'SDI6BHAF':[(3,3),(3,3),(5,5)]}
rows=[]
for key,items in FACTS.items():
 path=pdf_for(key);raw=subprocess.check_output(['pdftotext','-layout',str(path),'-'],timeout=45).decode(errors='replace');pages=raw.split('\f')
 card=ROOT/f'16_PETW/05_Literature_Wiki/wiki/liang2_shared_library/sources/{key}.md'
 anchors=card.read_text().split('## Quantitative anchors')[1].split('## Physical anchors')[0]
 for index,(question,value,unit,token) in enumerate(items):
  # Require the anchor's stated physical page, not a coincidental number elsewhere.
  plain=re.sub(r'\s+',' ',token.replace(',',''))
  lo,hi=PAGE_HINT[key][index]
  candidates=[(i,p) for i,p in enumerate(pages) if lo<=i+1<=hi and plain in re.sub(r'\s+',' ',p.replace(',',''))]
  assert candidates,(key,question,token)
  i,page=candidates[0]
  rows.append(dict(group='B',id=f'B{len(rows)+1:02}',prompt='Extract the requested numeric value and unit from the supplied published PDF page. Answer only JSON: {"answer":number,"unit":"unit"}. Question: '+question+'\nPDF page text (page '+str(i+1)+'):\n'+page[:14000],answer=float(value),unit=unit,source=str(path)+'#page='+str(i+1),card=str(card),page=i+1,question=question))
 print(key,'pages',[r['page'] for r in rows if r['card']==str(card)],flush=True)
assert len(rows)==25,len(rows)
partial=[json.loads(s) for s in (OUT/'eval_partial.jsonl').read_text().splitlines()]
all_rows=sorted(partial+rows,key=lambda r:(r['group'],int(r['id'][1:])))
assert len(all_rows)==100 and {g:sum(x['group']==g for x in all_rows) for g in 'ABCD'}=={'A':40,'B':25,'C':20,'D':15}
(OUT/'eval_set.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in all_rows))
print('READY',len(all_rows),flush=True)
