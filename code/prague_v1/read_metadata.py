"""Read tiny TURDATA metadata workbook remotely without full ZIP."""
import sys,zipfile,io,xml.etree.ElementTree as ET,requests
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'data_survey_v1'))
from check_prague import Remote
u='https://zenodo.org/api/records/10655033/files/TURDATA_metadata_and_photos.zip/content'
r=requests.head(u,timeout=30)
a=Remote(u);a.n=int(r.headers['Content-Length'])
with zipfile.ZipFile(a) as z: b=z.read('TURDATA_metadata.xlsx')
with zipfile.ZipFile(io.BytesIO(b)) as w:
    shared=[]
    if 'xl/sharedStrings.xml' in w.namelist():
        root=ET.fromstring(w.read('xl/sharedStrings.xml'))
        shared=[''.join(t.text or '' for t in si.iter() if t.tag.endswith('}t')) for si in root]
    for sn in [x for x in w.namelist() if x.startswith('xl/worksheets/sheet') and x.endswith('.xml')]:
        root=ET.fromstring(w.read(sn));print('SHEET',sn)
        for row in [e for e in root.iter() if e.tag.endswith('}row')]:
            vals=[]
            for c in row:
                if not c.tag.endswith('}c'):continue
                v=next((e.text for e in c.iter() if e.tag.endswith('}v')),None)
                if v is not None and c.attrib.get('t')=='s':v=shared[int(v)]
                if v:vals.append(v)
            if vals:print(' | '.join(vals))
print('bytes_fetched',a.bytes)
