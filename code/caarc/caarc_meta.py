import hashlib
import json
import re
import sys
from pathlib import Path

PROVENANCE = dict(case='CAARC M4 C05 02A smooth_v4', cells=2591745,
    mesh_count_correction='2,591,745 replaces erroneous building_v1 nominal count 2,892,045',
    coordinates=dict(frame='mesh coordinates, no rotation', x='+x inflow', y='crosswind', z='height', U=['Ux','Uy','Uz'], p='kinematic pressure p/rho'),
    time_axis=dict(restart_directory='3000', identifier=['SIMPLE runTime.timeIndex','pressure solve ordinal within iteration'], simulation_time='OpenFOAM native Time', correspondence='one actual solve per system; no stitching, deduplication or overlap'))


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def boundary(p):
    types=re.findall(r'\btype\s+(\w+)\s*;',p.read_text())
    assert len(types)==11 and set(types)<={'patch','symmetryPlane','symmetry','wall'}, types
    print(json.dumps(types))


def annotate(root):
    cfg=digest(root/'dump.config.sha256')
    for p in sorted((root/'dump/Solving').glob('*/meta.json')):
        m=json.loads(p.read_text()); assert not (m.keys() & PROVENANCE.keys())
        m.update(PROVENANCE,config_manifest_sha256=cfg)
        tmp=p.with_name('meta.annotated.tmp'); tmp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n'); tmp.replace(p)


def manifest(root):
    paths=[p for p in root.iterdir() if p.is_file() and not p.name.startswith(('product_manifest','log.manifest'))]
    paths.extend(p for p in (root/'dump/Solving').rglob('*') if p.is_file())
    for branch in ('dump','control'):
        paths.extend(p for p in (root/branch/'postProcessing').rglob('*') if p.is_file())
    paths.append(root/'frozen/CONFIG.sha256')
    systems=sorted((root/'dump/Solving').iterdir(),key=lambda p:tuple(map(int,p.name.split('-')[-2:])))
    summary=root/'summary_caarc.json'
    data=dict(PROVENANCE, openfoam_receipts='q1_caarc.csv: openfoam_receipt; full logs log.dump and log.control',
        first_system=systems[0].name if systems else None,
        first_system_bytes=sum(p.stat().st_size for p in systems[0].iterdir()) if systems else None,
        audit=json.loads(summary.read_text()) if summary.is_file() else None,
        manifest_scope='Scientific outputs and closed stage logs. Scheduler stdout/exit status are recorded separately after completion.',
        files=[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(set(paths))])
    with (root/'product_manifest.json').open('x') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
    (root/'product_manifest.sha256').write_text(digest(root/'product_manifest.json')+'  product_manifest.json\n')

if __name__=='__main__':
    {'boundary':boundary,'annotate':annotate,'manifest':manifest}[sys.argv[1]](Path(sys.argv[2]))
