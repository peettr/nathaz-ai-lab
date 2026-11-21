#!/usr/bin/env python3
"""Only inlet and top boundary variants on the copied SA case."""
import re,sys
from pathlib import Path
c=Path(sys.argv[1]); nu_text=(c/'constant/transportProperties').read_text()
m=re.search(r'\bnu\s*\[[^]]+\]\s*([\deE.+-]+)\s*;',nu_text); assert m, 'nu missing'
nu=float(m[1]); val=3*nu; assert 0<nu<1e-3
for field in ('U','nuTilda','p'):
 p=c/'0'/field; text=p.read_text()
 if field=='U':
  inlet='inlet { type fixedValue; value uniform (10 0 0); }'; top='top { type slip; }'
 elif field=='nuTilda':
  inlet=f'inlet {{ type fixedValue; value uniform {val:.12g}; }}'; top='top { type zeroGradient; }'
 else:
  inlet=None;top='top { type zeroGradient; }'
 if inlet:
  text,k=re.subn(r'\binlet\s*\{[^{}]*\}',inlet,text,count=1,flags=re.S);assert k==1,(field,'inlet')
 text,k=re.subn(r'\btop\s*\{[^{}]*\}',top,text,count=1,flags=re.S);assert k==1,(field,'top')
 p.write_text(text)
print('UNIFORM_SLIP_OK nu=',nu,'nuTilda=',val, 'top_patch=patch')
