#!/usr/bin/env python3
"""Generate a 5MW power-balance pitch curve from ROSCO NREL5MW Cp table and build new FF binary.
Above Cp table support, extrapolation is explicitly flagged as an assumption.
"""
from pathlib import Path
import math, shutil, subprocess
import numpy as np
B=Path('./lab_a3/downburst_ff')
SRC=B/'rosco210_ff_src'; DST=B/'rosco210_ff_src_curve_v1'; BUILD=B/'rosco210_ff_build_curve_v1'
TABLE=B/'ff_smoke_feedback/Cp_Ct_Cq.NREL5MW.txt'
CURVE=B/'segment_a_v4_curve.txt'
if any(p.exists() for p in (DST,BUILD,CURVE)):raise RuntimeError('refuse overwrite existing build/curve')
lines=TABLE.read_text().splitlines(); pitch=np.fromstring(lines[4],sep=' ');tsr=np.fromstring(lines[6],sep=' ')
cp=np.array([np.fromstring(l,sep=' ') for l in lines[12:38]])
assert cp.shape==(26,36)
wind=np.arange(8,61,.5)
values=[]
for U in wind:
    if U<=11.4: values.append(0.0); continue
    if U>=35:
        values.append(float(np.interp(35,[34,35],[0,30])+max(0,U-35)*.95))
        continue
    lam=np.clip((12.1*2*math.pi/60)*63/U,tsr[0],tsr[-1]); c=np.array([np.interp(lam,tsr,cp[:,j]) for j in range(len(pitch))]);
    target=5e6/(.944*.5*1.225*math.pi*63**2*U**3)
    xs=pitch[pitch>=0];ys=c[pitch>=0];k=int(np.argmax(ys));val=float(np.interp(target,ys[k:][::-1],xs[k:][::-1]));values.append(val)
# above >=35 pitch is an extrapolation, not supported by table; avoid discontinuity
v35=float(np.interp(34.5,wind,values));
for i,U in enumerate(wind):
    if U>=35:values[i]=v35+.95*(U-34.5)
CURVE.write_text('# ROSCO NREL5MW Cp table power balance to 34.5 m/s; above: assumed +0.95 deg/(m/s)\n'+''.join(f'{u:.3f} {v:.6f}\n' for u,v in zip(wind,values)))
shutil.copytree(SRC,DST)
p=DST/'src/Controllers.f90';s=p.read_text()
s=s.replace('    INTEGER, SAVE :: ff_n = 0, ff_idx = 1','    INTEGER, SAVE :: ff_n = 0, ff_idx = 1, ff_curve_n = 0\n    REAL(DbKi), ALLOCATABLE, SAVE :: ff_curve_u(:), ff_curve_pitch(:)')
s=s.replace('CHARACTER(4096) :: filename, gain_string, line','CHARACTER(4096) :: filename, gain_string, line, curve_path')
s=s.replace('REAL(DbKi) :: a, b, preview','REAL(DbKi) :: a, b, preview, p_preview, p_hub\n        INTEGER :: j')
needle='            WRITE(*,*) \'ROSCO_FF_INIT rows=\',ff_n,\' gain deg/(m/s)=\',ff_gain'
assert needle in s
s=s.replace(needle,"""            CALL get_environment_variable('ROSCO_FF_CURVE', curve_path, status=status)
            IF (status /= 0) ERROR STOP 'ROSCO FF: curve path required'
            OPEN(NEWUNIT=un, FILE=TRIM(curve_path), STATUS='old', ACTION='read', IOSTAT=ios)
            IF (ios /= 0) ERROR STOP 'ROSCO FF: cannot open 5MW pitch curve'
            ALLOCATE(ff_curve_u(1024),ff_curve_pitch(1024))
            DO
                READ(un,'(A)',IOSTAT=ios) line
                IF (ios < 0) EXIT
                IF (ios /= 0) ERROR STOP 'ROSCO FF curve read error'
                IF (LEN_TRIM(line)==0 .OR. line(1:1)=='#') CYCLE
                IF (ff_curve_n>=1024) ERROR STOP 'ROSCO FF too many curve rows'
                ff_curve_n=ff_curve_n+1
                READ(line,*,IOSTAT=ios) ff_curve_u(ff_curve_n),ff_curve_pitch(ff_curve_n)
                IF (ios/=0) ERROR STOP 'ROSCO FF curve format'
            END DO
            CLOSE(un)
            IF (ff_curve_n<2) ERROR STOP 'ROSCO FF curve too short'
"""+needle)
needle='        pitch=ff_gain*(preview-hub_u)*PI/180.0_DbKi'
assert needle in s
s=s.replace(needle,"""        p_preview=ff_curve_pitch(1)
        p_hub=ff_curve_pitch(1)
        DO j=1,ff_curve_n-1
            IF (preview>=ff_curve_u(j) .AND. preview<ff_curve_u(j+1)) &
              p_preview=ff_curve_pitch(j)+(ff_curve_pitch(j+1)-ff_curve_pitch(j))* &
                (preview-ff_curve_u(j))/(ff_curve_u(j+1)-ff_curve_u(j))
            IF (hub_u>=ff_curve_u(j) .AND. hub_u<ff_curve_u(j+1)) &
              p_hub=ff_curve_pitch(j)+(ff_curve_pitch(j+1)-ff_curve_pitch(j))* &
                (hub_u-ff_curve_u(j))/(ff_curve_u(j+1)-ff_curve_u(j))
        END DO
        IF (preview>=ff_curve_u(ff_curve_n)) p_preview=ff_curve_pitch(ff_curve_n)
        IF (hub_u>=ff_curve_u(ff_curve_n)) p_hub=ff_curve_pitch(ff_curve_n)
        pitch=ff_gain*(p_preview-p_hub)*PI/180.0_DbKi""")
p.write_text(s)
with (B/'segment_a_curve_build.log').open('w') as log:
    subprocess.run(['cmake','-S',str(DST),'-B',str(BUILD),'-DCMAKE_BUILD_TYPE=Release'],check=True,stdout=log,stderr=subprocess.STDOUT)
    subprocess.run(['cmake','--build',str(BUILD),'-j','4'],check=True,stdout=log,stderr=subprocess.STDOUT)
assert (BUILD/'libdiscon.so').exists()
print('curve',CURVE,'build',BUILD/'libdiscon.so')
