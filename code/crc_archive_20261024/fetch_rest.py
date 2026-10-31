"""Complete April 2024 public ERA5/HRRR inputs on CRC, disjoint from days 01-10."""
import os
import sys
import zipfile
from fetch_archives import ROOT, BASE, HTTPRange

if __name__ == '__main__':
    z = zipfile.ZipFile(HTTPRange(BASE+'data.zip'))
    wanted = {f'{i:02d}' for i in range(11,31)}
    dest = os.path.join(ROOT, 'repo', 'AERO_ODE')
    for info in z.infolist():
        name = info.filename
        if info.is_dir() or not (name.startswith('data/era5_test/') or name.startswith('data/hrrr_test/')):
            continue
        if not any(f'/04/{d}/' in name or f'/04/{d}.' in name for d in wanted):
            continue
        if os.path.isabs(name) or '..' in name.split('/'):
            raise ValueError(name)
        target = os.path.join(dest, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.exists(target):
            raise FileExistsError(target)
        print('extract', name, info.file_size, flush=True)
        with z.open(info) as src, open(target,'xb') as output:
            while data := src.read(1024*1024):
                output.write(data)
