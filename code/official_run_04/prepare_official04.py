#!/usr/bin/env python3
"""Prepare isolated AIR/Surface copies with batch-boundary GPU cleanup only."""
from pathlib import Path
import sys
root, run = map(Path, sys.argv[1:3])
repo = root / 'repo/AERO_ODE'
header = '''import sys as _sys
_sys.path.insert(0, "{repo}")
_sys.path.insert(0, "{local}")
from common.paths import ROOT
'''
old = '''import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(next(_p for _p in _pathlib.Path(__file__).resolve().parents
                             if (_p / "common" / "paths.py").is_file())))
from common.paths import ROOT
'''
for dirname, filename, variables, marker in [
    ('AERO_AIR_WD', 'test_film_wb.py',
     't_pred t_phy gt_hrrr t_phy_norm correction_norm dyn_in static_in output_chunks output output_flat gt_flat pred_list gt_list sgs_increment state_next state_pre state_post dyn sta s h m steps_all hours_all months_all input_std input_mean',
     '        if log:\n            print(f"Rank {rank} finished loader loop'),
    ('AERO_Surface_WD', 'test_film_00z_RMSE.py',
     't_pred t_phy gt t_phy_norm corr_norm solar_feat dyn_in static_in pred_chunks pred_all pred_flat gt_flat pred_list gt_list output_norm pred dyn sta s h m steps hours months mse',
     '                if MAX_BATCHES > 0 and int(count.item()) >= MAX_BATCHES:'),
]:
    source = repo / dirname / filename
    text = source.read_text()
    assert text.count(old) == 1, (source, 'header')
    text = text.replace(old, header.format(repo=repo, local=source.parent))
    assert text.count(marker) == 1, (source, 'marker')
    cleanup = '                del ' + ', '.join(variables.split()) + '\n                torch.cuda.empty_cache()\n'
    if dirname == 'AERO_AIR_WD':
        # Marker at the dedented end of the loader loop; keep cleanup inside it.
        text = text.replace(marker, cleanup + '\n' + marker)
    else:
        # Surface break must be after cleanup to release memory even on final sample.
        text = text.replace(marker, cleanup + '\n' + marker)
    (run / filename).write_text(text)
