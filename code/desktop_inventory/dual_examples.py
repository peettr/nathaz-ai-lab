import csv,sqlite3,re,pathlib
B=pathlib.Path(__file__).parent;d=sqlite3.connect('file:./ftkb_desktop/page_text_v2.sqlite?mode=ro',uri=True)
chosen=['620372dc','55d757ce','899c4337','2d8d1cdc','c0b3a3ce','1bda4236','be6539a8','907ca5f0','745178ce','967d3f55']
qa={r['sha256'][:8]:r for r in csv.DictReader((B/'dual_column_50.csv').open())}
rows=[]
for key in chosen:
 r=qa[key];t=d.execute('select text from pages where sha256=? and physical_page=?',(r['sha256'],r['page'])).fetchone()[0] or '';t=re.sub(r'\s+',' ',t);left=r['old_interleaved'].split(' | ')[0][:35];pos=t.find(left)
 assert pos>=0,(key,left)
 rows.append(dict(sha256=r['sha256'],physical_page=r['page'],old_interleaved=r['old_interleaved'],new_contiguous=t[max(0,pos-35):pos+230],note='局部左栏句子恢复连续；未证明整页顺序正确'))
with (B/'dual_column_examples_10.csv').open('w',encoding='utf8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print(len(rows))
