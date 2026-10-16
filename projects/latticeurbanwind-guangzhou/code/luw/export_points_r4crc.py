"""Export 80 western wind-tunnel points for stdlib-only CRC sampling."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).parent/'pydeps'))
import xlrd
base=Path(__file__).parent
book=xlrd.open_workbook('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls')
p=book.sheet_by_name('Geometry&Points')
rows=[]
for i in range(2,82):
 rid=int(p.cell_value(i,1));x=float(p.cell_value(i,2));y=float(p.cell_value(i,3))
 rows.append({'id':rid,'xls_xy':[x,y], 'local_xy':[x+1010.50008-300,y+1000.60004-650], 'before':float(book.sheet_by_name('Results (Before Construction)').cell_value(i+1,14)), 'after':float(book.sheet_by_name('Results (After Construction)').cell_value(i+1,14))})
assert len(rows)==80 and len({r['id'] for r in rows})==80
(base/'points_w_r4crc.json').write_text(json.dumps({'uref':3.9286416,'rows':rows,'registration':'xls XY=raw STL XY, same axes; PF=raw+(1010.50008,1000.60004,-0.10)m; crop raw x300 y650'},indent=2))
print('exported',len(rows), 'western points')
