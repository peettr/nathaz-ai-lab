#!/usr/bin/env python3
"""Reproduce a 60 s ROSCO NREL-5MW steady-wind OpenFAST smoke test."""
from pathlib import Path
import shutil
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOURCE = Path('./lab_a3/src/rosco-v2.10.6/Examples/Test_Cases/NREL-5MW')
RUN = Path('./lab_a3/run_nrel5mw_rosco_60s')
OUT = Path('./22_Lab/06_Logs/a3_turbine/smoke')

def prepare():
    if RUN.exists():
        raise RuntimeError(f'Refusing to overwrite existing run directory: {RUN}')
    shutil.copytree(SOURCE, RUN)
    f = RUN/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat'
    text = f.read_text()
    assert '"DISCON_LIB_PATH"' in text
    f.write_text(text.replace('"DISCON_LIB_PATH"', '"./lab_a3/env/lib/libdiscon.so"'))
    print(f'Run directory: {RUN}\nDeck: {RUN / "NREL-5MW.fst"}\n60 s, 8 m/s steady wind, ROSCO 2.10.6')

def plot(run=RUN, label='8ms'):
    file = run/'NREL-5MW.out'
    if not file.exists():
        raise RuntimeError(f'Expected text output absent: {file}')
    # OpenFAST text header followed by channel and unit rows, then numerical rows.
    lines = file.read_text().splitlines()
    header = next(i for i,line in enumerate(lines) if line.split()[:1] == ['Time'])
    names = lines[header].split()
    vals = np.loadtxt(file, skiprows=header+2)
    assert np.isfinite(vals).all() and vals.shape[0] > 10
    channels = ['Time', 'TwrBsMyt', 'BldPitch1']
    columns = {name: vals[:,names.index(name)] for name in channels}
    t = columns['Time']; assert abs(t[-1] - 60) < 0.02
    fig,axs = plt.subplots(2,1,figsize=(9,6),sharex=True,layout='constrained')
    axs[0].plot(t, columns['TwrBsMyt'],lw=1,color='#136799')
    axs[0].set_ylabel('Tower base fore-aft moment (kN m)')
    axs[1].plot(t, columns['BldPitch1'],lw=1,color='#b75c2e')
    axs[1].set_ylabel('Blade 1 pitch (deg)');axs[1].set_xlabel('Time (s)')
    for ax in axs:ax.grid(alpha=0.25)
    fig.suptitle('NREL 5-MW onshore · OpenFAST 5.0.0 / ROSCO 2.10.6')
    fig.text(0.5,0.005,f'Source: ROSCO v2.10.6 Examples/Test_Cases/NREL-5MW; steady {label.replace("ms", " m/s")}; 60 s; 工作站 WSL CPU',ha='center',fontsize=8)
    dest=OUT/f'nrel5mw_rosco_tower_pitch_{label}.png'; fig.savefig(dest,dpi=160,bbox_inches='tight'); print(f'Plot: {dest}')
    print('shape=',vals.shape,'last_time=',t[-1], 'channels=',channels)
    print('tower moment range=',(columns['TwrBsMyt'].min(),columns['TwrBsMyt'].max()),'pitch range=',(columns['BldPitch1'].min(),columns['BldPitch1'].max()))
    shutil.copy2(file,OUT/f'NREL-5MW_{label}.out')
    for suffix in ['.sum', '.ech']:
        p=run/('NREL-5MW'+suffix)
        if p.exists():shutil.copy2(p,OUT/f'NREL-5MW_{label}{suffix}')
if __name__ == '__main__':
    if sys.argv[1]=='plot14': plot(Path('./lab_a3/run_nrel5mw_rosco_14ms_v2_60s'),'14ms')
    elif sys.argv[1]=='plot8': plot(RUN,'8ms')
    elif sys.argv[1]=='prepare': prepare()
