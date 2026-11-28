#!/usr/bin/env python3
"""L26.11 C_M3' (11-24, 参谋批，委托 #b4c4414a): coarse C_M3 with the author's PAPER-VERSION DEScover code (commit f17f4d1).
Generates C_M3 exactly as make_case_c.py (sha 512a3ca8) does, then changes ONLY:
  - controlDict libs: libDEScoverDelta_v3.so -> libDEScoverPaper_f17f4d1.so
  - turbulenceProperties: LESModel SpalartAllmarasIDDES -> SpalartAllmarasIDDESPaper (author's modified SA-IDDES, class renamed only);
    delta IDDESDeltaDEScover (v3 coupling) -> IDDESDeltaPaper (author's IDDESDelta, class renamed only); hmaxOuter DeltaLiutexTilde (author's f17f4d1).
  Coefficients identical to C_M3: Cw 0.15, fdLimit 0.01, Clim 0.15, deltaCoeff 1.035; SA-IDDES coefficients at defaults (Cdt1 8, Cdt2 3, Cl 3.55, Ct 1.63).
usage: make_case_c_paper.py <outdir>"""
import os, sys, subprocess
out = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
subprocess.check_call([sys.executable, os.path.join(here, 'make_case_c.py'), out, 'M3'], stdout=subprocess.DEVNULL)
cd = os.path.join(out, 'system/controlDict'); c = open(cd).read()
old = 'lib/libDEScoverDelta_v3.so'
assert c.count(old) == 1; c = c.replace(old, 'lib/libDEScoverPaper_f17f4d1.so'); open(cd, 'w').write(c)
tp = os.path.join(out, 'constant/turbulenceProperties'); t = open(tp).read()
hdr = t.split('simulationType')[0]
les = """simulationType LES;
LES
{
    LESModel        SpalartAllmarasIDDESPaper;   // author's paper-version SA-IDDES (DEScover f17f4d1), class renamed only
    turbulence      on;
    printCoeffs     on;
    delta           IDDESDeltaPaper;             // author's paper-version IDDESDelta (f17f4d1), class renamed only
    IDDESDeltaPaperCoeffs
    {
        Cw          0.15;
        fdLimit     0.01;
        Clim        0.15;
        hmaxOuter   DeltaLiutexTilde;            // author's DeltaLiutexTildeDelta (f17f4d1), unchanged
        DeltaLiutexTildeCoeffs
        {
            deltaCoeff  1.035;
        }
    }
}
"""
open(tp, 'w').write(hdr + les)
print('written', out, "C_M3'")
