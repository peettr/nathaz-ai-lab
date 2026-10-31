"""Build PDF-page tasks only from card numeric anchors verified in published PDF text."""
import json,re,sqlite3,subprocess
from pathlib import Path
ROOT=Path('./');OUT=Path(__file__).parent;WIKI=ROOT/'16_PETW/05_Literature_Wiki/wiki'
con=sqlite3.connect('file:./Zotero/zotero.sqlite?immutable=1',uri=True)
# key,page,table,question,answer,unit,card_numeric_anchor_snippet
FACTS=[
 ('K6H584AX',4,1,'In Table 1, what is the mean y0? Give km.',.50,'km','y0 mean 0.50 km'),
 ('K6H584AX',4,1,'In Table 1, what is the coefficient of variation (COV) for zmax?',.11,'1','zmax mean 75.00 m COV 0.11'),
 ('K6H584AX',9,2,'In Table 2, Case 1 (Li shape scaling), what is the average total Sobol index ST for Vmax?',.46,'1','Vmax 0.41/0.48/0.46'),
 ('K6H584AX',9,2,'In Table 2, Case 2 (vertical profile models), what is the average total Sobol index ST for y0?',.15,'1','y0 0.15/0.24/0.18 and 0.10/0.19/0.15'),
 ('K6H584AX',9,2,'In Table 2, Case 2, what is the average total Sobol index ST for rmax?',.17,'1','rmax 0.11/0.17/0.13 and 0.11/0.30/0.17'),
 ('K6H584AX',9,3,'In Table 3, what is the average total Sobol index ST for Vmax?',.47,'1','Vmax 0.39/0.55/0.47'),
 ('K6H584AX',9,3,'In Table 3, what is the maximum total Sobol index ST for y0?',.22,'1','y0 0.07/0.22/0.16'),
 ('K6H584AX',11,4,'In Table 4, what is the mean maximum roof drift for Solari PSD? Use the table numerical value, in percent.',.237,'%','Solari 0.237/0.207/0.343'),
 ('K6H584AX',11,4,'In Table 4, what is the COV for Kaimal PSD?',.228,'1','Kaimal 0.220/0.228/0.324'),
 ('K6H584AX',11,4,'In Table 4, what is the 95th percentile maximum roof drift for Davenport PSD, in percent?',.306,'%','Davenport 0.223/0.190/0.306'),
 ('234HE2EZ',2,1,'In Table 1, what is Vmax for Exposure C under Criterion 1, in m/s?',89.47,'m/s','89.47'),
 ('234HE2EZ',2,1,'In Table 1, what is zmax for Exposure B, in m?',80.47,'m','80.47'),
 ('234HE2EZ',2,1,'In Table 1, what is Vmax for Exposure A under Criterion 2, in m/s?',45.15,'m/s','45.15'),
 ('234HE2EZ',7,2,'In Table 2, what is the expected maximum for Case 1, in m?',.1004,'m','0.1004'),
 ('234HE2EZ',7,2,'In Table 2, what is sub-factor I3 for Case 1?',.9012,'1','0.9012'),
 ('234HE2EZ',8,3,'In Table 3 for td=10 s, what is the G-F/B-L ratio of base shear?',1.67,'1','1.67'),
 ('234HE2EZ',8,3,'In Table 3 for td=200 s, what is the G-F/B-L ratio of bending moment?',1.34,'1','1.34'),
 ('2HND5GK3',2,1,'In Table 1, what is the height of maximum horizontal velocity for Wood et al. (2001), as a multiple of D?',.016,'D','0.016D'),
 ('2HND5GK3',2,1,'In Table 1, what is the radial position of maximum horizontal velocity for Wood et al. (2001), as a multiple of D?',1.5,'D','1.5D'),
 ('LQHR4SX7',4,0,'What is the test-model wind-profile power-law exponent?',.15,'1','0.15'),
 ('LQHR4SX7',5,0,'What is the equivalent sectional density of the model, in kg/m3?',279.1,'kg/m3','279.1'),
 ('KGR5FYSB',3,0,'What downburst scaling diameter is assumed, in m?',660,'m','660'),
 ('3R5RN3GT',10,1,'In Table 1 for the downburst at Node 2, what is the Wavelet mean extreme displacement response in m?',.00920,'m','0.00920'),
 ('WVGZ39GL',7,2,'In Table 2 for Example 2, what is the numerical maximum sigma_G-F(t)?',.010,'1','0.010'),
 ('5NVCLN7I',3,2,'In Table 2, what is the FEM frequency of the first tower fore-aft mode in Hz?',.33,'Hz','0.33'),
]
assert len(FACTS)==25 and len({x[0] for x in FACTS})==8 and sum(x[2]>0 for x in FACTS)>=20
CARD={k:(WIKI/'step4c_structural_response/detailed_readings'/f'{k}.md' if (WIKI/'step4c_structural_response/detailed_readings'/f'{k}.md').exists() else next(WIKI.rglob(k+'.md'))) for k in {x[0] for x in FACTS}}
def pdf_for(key):
 rec=con.execute('select i.key,a.path from itemAttachments a join items i on i.itemID=a.itemID join items p on p.itemID=a.parentItemID where p.key=? and a.path like "%.pdf"',(key,)).fetchone()
 assert rec,key
 path=Path('./Zotero/storage')/rec[0]/rec[1].removeprefix('storage:');assert path.exists(),path
 return path
cache={};new=[]
for key,page,table,question,answer,unit,anchor in FACTS:
 card=CARD[key];s=card.read_text(errors='replace');assert anchor in s,(key,anchor)
 path=pdf_for(key);ci=(str(path),page)
 if ci not in cache:cache[ci]=subprocess.check_output(['pdftotext','-f',str(page),'-l',str(page),'-layout',str(path),'-'],timeout=45).decode(errors='replace')
 text=cache[ci];token=[已隐去],'g')
 # Check a distinct numeric token in the actual PDF page; tolerance of leading zero in decimal notation.
 assert any(abs(float(n.replace(',',''))-answer)<max(1e-8,abs(answer)*1e-5) for n in re.findall(r'(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])',text)),(key,page,token)
 if table:assert re.search(r'\bTable\s*'+str(table)+r'\b',text,re.I),(key,page,table)
 new.append(dict(group='B2',id=f'B2_{len(new)+26:03}',prompt='Extract the requested numeric value and unit from the supplied published PDF page. Answer only JSON: {"answer":number,"unit":"unit"}. Question: '+question+'\nPDF page text (page '+str(page)+'):\n'+text[:14000],answer=answer,unit=unit,source=str(path)+'#page='+str(page),card=str(card),page=page,question=question,table=table,card_anchor=anchor))
old=[json.loads(s) for s in (OUT/'eval_set_v3.jsonl').read_text().splitlines() if json.loads(s)['group']=='B']
assert len(old)==25
for i,x in enumerate(old,1):
 x['id']=f'B2_{i:03}';x['group']='B2';x['table']=0
allb=old+new
assert len(allb)==50 and len(set(x['card'] for x in allb))>=15
(OUT/'eval_b_r2_draft.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in allb))
print('B READY',len(allb),'papers',len(set(x['card'] for x in allb)),'table',sum(x['table']>0 for x in allb))
