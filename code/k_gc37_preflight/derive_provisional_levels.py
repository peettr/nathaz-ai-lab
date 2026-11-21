#!/usr/bin/env python3
"""Derive provisional common levels from archived actual WPS readback.

Does not claim validation against currently accessible raw NCAR GFS files.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
READBACK = Path('./22_Lab/06_Logs/k_wrf_drivers/v22/READBACK_v22.json')
GC37_HPA = (1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000)
GROUPS = ('G24', 'G48', 'G72')

def main():
    d = json.loads(READBACK.read_text())
    all_levels = []
    first_last = []
    for group in GROUPS:
        entries = [e for e in d['files'] if e['file'].startswith(group + '/')]
        if not entries:
            raise ValueError(f'missing {group} historical readback')
        first_last.append((group, entries[0]['file'], entries[-1]['file'], len(entries)))
        for entry in entries:
            all_levels.append(tuple(entry['complete_levels_pa']))
    if len(set(all_levels)) != 1:
        raise ValueError('historical GFS levels vary between files')
    gfs = tuple(int(x // 100) for x in all_levels[0])
    if any(x % 100 for x in all_levels[0]) or len(gfs) != len(set(gfs)):
        raise ValueError('bad pressure-level metadata')
    common = tuple(sorted(set(gfs) & set(GC37_HPA), reverse=True))
    for name, values in (('GFS_202006_levels_PROVISIONAL.txt', gfs), ('GC37_GFS_common_levels_PROVISIONAL.txt', common)):
        path = ROOT / name
        with path.open('x') as f:
            f.write('# PROVISIONAL: historical v2.2 WPS readback, not live NCAR raw-file verification\n')
            f.write(f'# source: {READBACK}\n')
            f.write('# units: hPa; surface-to-top order\n')
            for level in values:
                f.write(f'{level}\n')
    print(json.dumps({'historical_files_checked': len(all_levels), 'cycles': first_last, 'gfs_levels_hpa': gfs, 'common_levels_hpa': common, 'common_count': len(common), 'raw_archive_verified_now': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
