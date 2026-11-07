"""Create MIT Task52 wrapper adapter for OpenFAST5 extended lidar channels."""
from pathlib import Path
import shutil,tarfile
root=Path(__file__).resolve().parent
src=Path('./lab_a3/downburst_ff/LidarAssistedControl/WRAPPER')
dst=root/'wrapper_B3_extended_adapter_src'
assert not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.git','build','*.dll'))
p=dst/'src/WRAPPER.f90';s=p.read_text()
# This bridge only adapts the old author's avrSWAP layout; LDP/FFP/ROSCO unmodified.
needle='RootName = TRANSFER(avcOUTNAME, RootName)'
assert s.count(needle)==1
s=s.replace(needle,'''! OpenFAST5 extended lidar measurements are 2001:2500 (not old avrSWAP(63)).
! Reserve a legacy-shaped, non-overlapping slice within that group for the
! author's single-beam LDP->FFP->ROSCO chain.  No model/control changes.
IF (NINT(avrSWAP(2001)) == 1 .AND. NINT(avrSWAP(2002)) >= 1) THEN
    avrSWAP(63)   = 2100.0_C_FLOAT
    avrSWAP(2100) = 1.0_C_FLOAT ! fresh measurement (single point)
    avrSWAP(2101) = 1.0_C_FLOAT ! beam ID
    avrSWAP(2102) = 1.0_C_FLOAT ! one gate
    avrSWAP(2103) = avrSWAP(2005) ! upstream x-wind estimate, not LOS radial velocity
ELSE
    avrSWAP(63)   = 2100.0_C_FLOAT
    avrSWAP(2100) = 0.0_C_FLOAT
    avrSWAP(2101) = 1.0_C_FLOAT
    avrSWAP(2102) = 1.0_C_FLOAT
    avrSWAP(2103) = 999.0_C_FLOAT
ENDIF
IF (NINT(avrSWAP(1)) == 0) PRINT *, 'A3_B3_BRIDGE sensor,beams,gate,x=', &
    avrSWAP(2001),avrSWAP(2002),avrSWAP(2003),avrSWAP(2005)
'''+needle)
# 63 is legacy logging pointer; preserve it on return from wrapper rather than clobbering.
s=s.replace('RootName = TRANSFER(avcOUTNAME, RootName)','RootName = TRANSFER(avcOUTNAME, RootName)',1)
p.write_text(s)
archive=root/'wrapper_B3_extended_adapter_src.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'x:gz') as f:f.add(dst,arcname=dst.name)
print(archive,archive.stat().st_size)
