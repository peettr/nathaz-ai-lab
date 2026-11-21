from pathlib import Path
import re
root=Path('/groups/kareem/[用户]/L26_21_DAFOAM_20261114_d0f')
for grade in ('coarse','medium'):
 b=(root/'cases'/grade/'constant/polyMesh/boundary').read_text('latin1')
 blocks=re.findall(r'(?m)^    ([A-Za-z]\w*)\n    \{\n(.*?)\n    \}',b,re.S)
 patch={name:re.search(r'\btype\s+(\w+)\s*;',body).group(1) for name,body in blocks}
 expected={'inlet','outlet','sideNeg','sidePos','ground','top','xneg','xpos','yneg','ypos','roof'}
 assert set(patch)==expected,(grade,patch)
 for field in ('U','p','k','omega','nut'):
  text=(root/'cases'/grade/'0'/field).read_text()
  groups=re.findall(r'(?m)("\(sideNeg\|sidePos\|top\)"|\b(?:inlet|outlet|ground|xneg|xpos|yneg|ypos|roof))\s*\{([^{}]*)\}',text)
  assert len(groups)==9,(grade,field,groups)
  names=set()
  for name,body in groups:
   ty=re.search(r'\btype\s+(\w+)\s*;',body)
   assert ty,(grade,field,name)
   expanded=('sideNeg','sidePos','top') if name.startswith('"') else (name,)
   for n in expanded:
    assert n not in names,(grade,field,n)
    names.add(n)
    if patch[n]=='symmetryPlane': assert ty.group(1)=='symmetryPlane',(grade,field,n,ty.group(1))
  assert names==expected,(grade,field,names)
  print(grade,field,'ALL_11_PATCHES_MATCH',flush=True)
