#!/usr/bin/env python3
"""Patch only a fail-closed initialization-only native flags gate."""
import sys
from pathlib import Path
p=Path(sys.argv[1]); s=p.read_text()
anchor='''                                "Profile boundary conditions completed",
                                1ll,
                                1ll,
                                false);
            print_kv_row("Boundary init", "complete. Time: [" + now_str() + "]");

            if (flux_correction) {'''
assert s.count(anchor)==1
insert='''                                "Profile boundary conditions completed",
                                1ll,
                                1ll,
                                false);
            print_kv_row("Boundary init", "complete. Time: [" + now_str() + "]");
            // Case A v2: boundary-complete native host flags; no time advancement.
            if (std::getenv("LUW_CASEA_GEOM_GATE_ONLY") != nullptr) {
            const std::string flag_path = parent + "/native_flags_voxel.u8";
            std::ofstream out(flag_path, std::ios::binary | std::ios::trunc);
            if (!out) { println("ERROR: cannot open native flag output"); exit(91); }
            for (ulong n=0ull; n<lbm.get_N(); n++) {
                const uchar value = lbm.flags[n];
                out.write(reinterpret_cast<const char*>(&value), 1);
            }
            out.close();
            if (!out) { println("ERROR: native flag export incomplete"); exit(92); }
            println("| GEOM_GATE_NATIVE_FLAGS dims=" + to_string(lbm.get_Nx()) + "," +
                    to_string(lbm.get_Ny()) + "," + to_string(lbm.get_Nz()) +
                    " bytes=" + to_string(lbm.get_N()) + " path=" + flag_path + " |");
                return;
            }

            if (flux_correction) {'''
s=s.replace(anchor,insert)
p.write_text(s)
print('patched',p)
