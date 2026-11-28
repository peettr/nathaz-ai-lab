#!/usr/bin/env python3
"""Prepare isolated try11 OpenCL fixture variants; never run solver locally."""
from pathlib import Path
import shutil, hashlib, json, tarfile, difflib
R=Path(__file__).resolve().parent
source=R.parent/'try9_fix2/FluidX3D_gate0'
assert source.is_dir() and not (R/'FluidX3D_gate0_noshear').exists()
assert not (R/'FluidX3D_gate0_shear').exists()
for variant in ('noshear','shear'):
    dst=R/f'FluidX3D_gate0_{variant}'
    shutil.copytree(source,dst)
    src=dst/'src'
    kp=src/'kernel.cpp'; old=kp.read_text(); new=old
    pairs=[
    ('t%2ul ? 16u : 15u','t%2ul ? 15u : 16u'),
    ('t%2ul ? 9u : 10u','t%2ul ? 10u : 9u'),
    ('t%2ul ? 18u : 17u','t%2ul ? 17u : 18u'),
    ('t%2ul ? 11u : 12u','t%2ul ? 12u : 11u'),
    ('t%2ul ? 10u : 9u','t%2ul ? 9u : 10u'),
    ('t%2ul ? 15u : 16u','t%2ul ? 16u : 15u'),
    ('t%2ul ? 12u : 11u','t%2ul ? 11u : 12u'),
    ('t%2ul ? 17u : 18u','t%2ul ? 18u : 17u')]
    lines=new.splitlines(keepends=True)
    for idx,pair in zip((1568,1570,1572,1574,1583,1584,1585,1586),pairs):
        line=lines[idx-1]
        assert line.count(pair[0])==1, (idx,line)
        lines[idx-1]=line.replace(*pair)
    new=''.join(lines)
    new=new.replace('// For even t, outgoing odd 15/17 was written into ground slot 15/17,\n\t// and outgoing even 10/12 into the source-fluid slot 9/11. Reverse slots at odd t.',
                    '// At even t, read the slot stored by the preceding odd step, not this step.\n\t// Outgoing f10/f12 at even t store into slots 10/12; reverse at odd t.')
    assert new!=old and 'At even t, read the slot stored' in new
    new=new.replace(')+"#ifndef WALL_GATE0"+R(\n\t\tif(flagsn_bo==TYPE_S)', '\t\tif(flagsn_bo==TYPE_S)')
    new=new.replace(')+"#endif"+R( // WALL_GATE0 preserves fixture-only solid DDF velocity\n)+"#else"+R( // MOVING_BOUNDARIES', ')+"#else"+R( // MOVING_BOUNDARIES')
    assert 'WALL_GATE0 preserves fixture-only' not in new
    if variant=='noshear':
        new=new.replace('if(usq>1.0e-16f) {','if(usq>1.0e-16f && false) {',1)
        assert 'if(usq>1.0e-16f && false)' in new
    kp.write_text(new)
    sp=src/'setup.cpp'; st=sp.read_text()
    st=st.replace('"/content/try9_fix2_wall_gate0.csv"',f'"/content/try11_{variant}_wall_gate0.csv"')
    st=st.replace('"/content/try9_fix2_wall_gate0_pulse.csv"',f'"/content/try11_{variant}_pulse.csv"')
    assert f'try11_{variant}_wall_gate0.csv' in st
    sp.write_text(st)
    (R/f'{variant}.patch').write_text(''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='try9_fix2/kernel.cpp',tofile=f'try11/{variant}/kernel.cpp')))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (kp,sp,src/'lbm.cpp',src/'defines.hpp')}
    archive=R/f'try11_{variant}.tar.gz'
    with tarfile.open(archive,'w:gz') as t:t.add(dst,arcname='FluidX3D_gate0')
    (R/f'try11_{variant}_manifest.json').write_text(json.dumps({'sources':hashes,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+'\n')
    print(variant,hashes,archive.stat().st_size)
