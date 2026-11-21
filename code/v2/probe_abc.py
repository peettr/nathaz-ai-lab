import pandas as pd
p='/content/l2613v2/LF_caseE.xls';a=pd.read_excel(p,sheet_name='Geometry&Points',header=None)
print('shape',a.shape)
for i,row in a.iterrows():
 s=' | '.join(str(v) for v in row if pd.notna(v))
 if any(str(v).strip() in ('A','B','C') for v in row):print(i,s)
print('tail',a.tail(30).to_string(index=False,header=False))
