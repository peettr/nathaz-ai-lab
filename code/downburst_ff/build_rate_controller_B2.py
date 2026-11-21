"""Create NEW Apache-2.0 ROSCO source archive, without touching prior run roots."""
from pathlib import Path
import shutil,tarfile
root=Path(__file__).resolve().parent
src=Path('./lab_a3/downburst_ff/rosco210_ff_src_guo_v2')
dst=root/'rosco210_ff_src_rate_B2'
if dst.exists():raise RuntimeError(f'refuse existing {dst}')
shutil.copytree(src,dst)
p=dst/'src/Controllers.f90';s=p.read_text()
def rep(old,new,count=1):
 global s
 assert s.count(old)==count,(old,s.count(old))
 s=s.replace(old,new,count)
rep('    LOGICAL, SAVE :: ff_initialized = .FALSE.','    LOGICAL, SAVE :: ff_initialized = .FALSE.\n    REAL(DbKi), SAVE :: ff_last_theta = 0.0_DbKi, ff_last_t = -1.0_DbKi')
rep('    SUBROUTINE PreviewPitchFF(t, hub_u, pitch)','    SUBROUTINE PreviewPitchFF(t, hub_u, pitch_rate)')
rep('        REAL(DbKi), INTENT(OUT) :: pitch','        REAL(DbKi), INTENT(OUT) :: pitch_rate')
rep('        REAL(DbKi) :: a, b, preview, p_preview, p_hub','        REAL(DbKi) :: a, b, preview, p_preview, p_hub, theta')
rep('        pitch = 0.0_DbKi','        pitch_rate = 0.0_DbKi')
rep('        pitch=ff_gain*p_preview*PI/180.0_DbKi','''        ! The input series has already been low-pass filtered and buffered.
        ! DIFFERENTIATE the steady-pitch reference; never add absolute theta to PI output.
        theta=ff_gain*p_preview*PI/180.0_DbKi
        IF (ff_last_t >= 0.0_DbKi .AND. t > ff_last_t) THEN
            pitch_rate=(theta-ff_last_theta)/(t-ff_last_t)
        END IF
        ff_last_t=t
        ff_last_theta=theta''')
rep('        REAL(DbKi) :: ff_pitch','        REAL(DbKi) :: ff_pitch_rate')
rep('''        LocalVar%PC_PitComT = PIController(LocalVar%PC_SpdErr, LocalVar%PC_KP, LocalVar%PC_KI, LocalVar%PC_MinPit, LocalVar%PC_MaxPit, LocalVar%DT, LocalVar%BlPitch(1), LocalVar%piP, LocalVar%restart, objInst%instPI)''','''        CALL PreviewPitchFF(LocalVar%Time, LocalVar%HorWindV, ff_pitch_rate)
        LocalVar%PC_PitComT = PIControllerRateFF(LocalVar%PC_SpdErr, LocalVar%PC_KP, LocalVar%PC_KI, ff_pitch_rate, LocalVar%PC_MinPit, LocalVar%PC_MaxPit, LocalVar%DT, LocalVar%BlPitch(1), LocalVar%piP, LocalVar%restart, objInst%instPI)''')
rep('''        ! A3 collective preview term BEFORE stock saturation and rate limiting.
        ! Same binary for all treatments; gain=0 for feedback.
        CALL PreviewPitchFF(LocalVar%Time, LocalVar%HorWindV, ff_pitch)
        LocalVar%PC_PitComT = LocalVar%PC_PitComT + ff_pitch
''','')
old=s[s.index('    REAL(DbKi) FUNCTION PIController(error, kp, ki, minValue'):s.index('    END FUNCTION PIController',s.index('    REAL(DbKi) FUNCTION PIController(error, kp, ki, minValue'))+len('    END FUNCTION PIController')]
new=old.replace('PIController','PIControllerRateFF').replace('error, kp, ki, minValue','error, kp, ki, ff_rate, minValue').replace('        REAL(DbKi),    INTENT(IN)         :: ki','        REAL(DbKi),    INTENT(IN)         :: ki\n        REAL(DbKi),    INTENT(IN)         :: ff_rate').replace('DT*ki*error','DT*(ki*error + ff_rate)')
rep(old,old+'\n\n    ! A3-B2: rate enters PI integrator before saturation (cf. Guo 2023 §4.4).\n'+new)
p.write_text(s)
archive=root/'rosco210_ff_src_rate_B2.tar.gz'
with tarfile.open(archive,'w:gz') as f:f.add(dst,arcname='rosco210_ff_src_rate_B2')
print(archive,archive.stat().st_size)
