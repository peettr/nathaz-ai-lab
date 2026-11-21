"""Parse final ASCII OpenFOAM cell centres in global cell order."""
import re
import numpy as np

def read_centres(path, expected):
    text=path.read_text()
    if not re.search(r'\bformat\s+ascii\s*;',text[:4096]):
        raise ValueError('cell centres must be ASCII')
    m=re.search(r'\binternalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(',text)
    if not m or int(m.group(1)) != expected:
        raise ValueError('cell centre count mismatch')
    tail=text[m.end():]
    end=re.search(r'(?m)^\s*\)\s*;\s*$',tail)
    if not end: raise ValueError('missing closing list delimiter')
    rows=re.findall(r'(?m)^\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*$',tail[:end.start()])
    if len(rows)!=expected: raise ValueError(f'{len(rows)} != {expected}')
    arr=np.asarray(rows,dtype=float)
    if not np.isfinite(arr).all(): raise ValueError('nonfinite centres')
    return arr
