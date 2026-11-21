#!/usr/bin/env python3
"""Stage isolated Apache-2.0 ROSCO 2.10.6 and inject a minimal scheduled collective FF.
Input file: monotonically increasing time[s], preview wind[m/s], already arrival-aligned.
ROSCO_FF_GAIN_DEG_PER_MS sets gain (zero for feedback); ROSCO_FF_FILE is CSV/whitespace.
This is an experimental controller, not the unlicensed LidarAssistedControl implementation.
"""
from pathlib import Path
import shutil
src=Path('./lab_a3/src/rosco-v2.10.6/rosco/controller')
dst=Path('./lab_a3/downburst_ff/rosco210_ff_src')
if dst.exists(): raise SystemExit(f'refuse overwrite {dst}')
shutil.copytree(src,dst)
p=dst/'src/Controllers.f90'; s=p.read_text()
s=s.replace('    IMPLICIT NONE\n\nCONTAINS', '''    IMPLICIT NONE
    ! Per-process, single turbine; loaded at first controller call.
    INTEGER, PARAMETER :: FF_MAX = 1000000
    REAL(DbKi), ALLOCATABLE, SAVE :: ff_t(:), ff_u(:)
    REAL(DbKi), SAVE :: ff_gain = 0.0_DbKi
    INTEGER, SAVE :: ff_n = 0, ff_idx = 1
    LOGICAL, SAVE :: ff_initialized = .FALSE.

CONTAINS
    SUBROUTINE PreviewPitchFF(t, hub_u, pitch)
        REAL(DbKi), INTENT(IN) :: t, hub_u
        REAL(DbKi), INTENT(OUT) :: pitch
        CHARACTER(4096) :: filename, gain_string, line
        REAL(DbKi) :: a, b, preview
        INTEGER :: status, ios, un
        pitch = 0.0_DbKi
        IF (.NOT. ff_initialized) THEN
            CALL get_environment_variable('ROSCO_FF_GAIN_DEG_PER_MS', gain_string, status=status)
            IF (status /= 0) ERROR STOP 'ROSCO FF: gain required (0 for feedback)'
            READ(gain_string, *, IOSTAT=ios) ff_gain
            IF (ios /= 0) ERROR STOP 'ROSCO FF: invalid gain'
            CALL get_environment_variable('ROSCO_FF_FILE', filename, status=status)
            IF (status /= 0) ERROR STOP 'ROSCO FF: timeseries required'
            OPEN(NEWUNIT=un, FILE=TRIM(filename), STATUS='old', ACTION='read', IOSTAT=ios)
            IF (ios /= 0) ERROR STOP 'ROSCO FF: cannot open timeseries'
            ALLOCATE(ff_t(FF_MAX), ff_u(FF_MAX))
            DO
                READ(un, '(A)', IOSTAT=ios) line
                IF (ios < 0) EXIT
                IF (ios /= 0) ERROR STOP 'ROSCO FF: file read failure'
                IF (LEN_TRIM(line)==0 .OR. line(1:1)=='#') CYCLE
                READ(line, *, IOSTAT=ios) a, b
                IF (ios /= 0) ERROR STOP 'ROSCO FF: expected time and wind'
                IF (ff_n >= FF_MAX) ERROR STOP 'ROSCO FF: too many rows'
                IF (ff_n > 0) THEN
                    IF (a <= ff_t(ff_n)) ERROR STOP 'ROSCO FF: times must increase'
                END IF
                ff_n=ff_n+1
                ff_t(ff_n)=a
                ff_u(ff_n)=b
            END DO
            CLOSE(un)
            IF (ff_n < 2) ERROR STOP 'ROSCO FF: at least two rows required'
            WRITE(*,*) 'ROSCO_FF_INIT rows=',ff_n,' gain deg/(m/s)=',ff_gain
            ff_initialized=.TRUE.
        END IF
        DO WHILE (ff_idx < ff_n-1)
            IF (ff_t(ff_idx+1) > t) EXIT
            ff_idx=ff_idx+1
        END DO
        IF (t <= ff_t(1)) THEN
            preview=ff_u(1)
        ELSE IF (t >= ff_t(ff_n)) THEN
            preview=ff_u(ff_n)
        ELSE
            preview=ff_u(ff_idx)+(ff_u(ff_idx+1)-ff_u(ff_idx))* &
                 (t-ff_t(ff_idx))/(ff_t(ff_idx+1)-ff_t(ff_idx))
        END IF
        ! Wind estimate is locally measured, so steady wind alone yields no offset.
        pitch=ff_gain*(preview-hub_u)*PI/180.0_DbKi
    END SUBROUTINE PreviewPitchFF''',1)
s=s.replace('        INTEGER(IntKi)                                  :: K            ! Index used for looping through blades.','        INTEGER(IntKi)                                  :: K            ! Index used for looping through blades.\n        REAL(DbKi) :: ff_pitch',1)
s=s.replace('        ! Saturate collective pitch commands:\n', '''        ! A3 collective preview term BEFORE stock saturation and rate limiting.
        ! Same binary for all treatments; gain=0 for feedback.
        CALL PreviewPitchFF(LocalVar%Time, LocalVar%HorWindV, ff_pitch)
        LocalVar%PC_PitComT = LocalVar%PC_PitComT + ff_pitch
        ! Saturate collective pitch commands:
''',1)
p.write_text(s)
print(dst)
