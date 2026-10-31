"""Adapt existing validated VTK extractor to the split experiment."""
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parent
for tag,source in [('E1',P/'resolution_crop_v2/extract_C1v2.py'),('E05',P/'resolution_c05/extract_c05.py'),('C1G0',P/'resolution_crop_v2/extract_C1v2.py')]:
 s=source.read_text()
 if tag=='E05':
  s=s.replace("Path('/content/luw_resolution_c05_v1')", "Path('/content/luw_split_E05')")
 else:
  s=s.replace("Path('/content/luw_crop_v2_C1v2')",f"Path('/content/luw_split_{tag}')")
 if tag.startswith('E'):
  s=s.replace('assert count==2756;tri=tri[:-12]','assert count==12;tri=[]').replace('assert count==2756;tri=tri[:-12]','assert count==12;tri=[]')
  s=s.replace('assert count==2756','assert count==12')
  # STL sections are empty by construction: no mask section geometry.
  s=s.replace('for t in tri:', 'for t in tri:')
 # All five upstream stations, full 1..30m profiles.
 s=s.replace('for xsite in (5.,25.,42.):','for xsite in (5.,15.,25.,35.,42.):')
 s=s.replace('for xsite in (5., 25., 42.):','for xsite in (5.,15.,25.,35.,42.):')
 # Empty STL has no building z=2 mask; mask fit loop works on zero predicted surfaces.
 (R/(f'extract_{tag}.py')).write_text(s)
 print(tag,len(s))
