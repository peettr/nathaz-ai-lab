#!/usr/bin/env python3
"""Host syntax and emitted OpenCL checks; never invokes a solver."""
import hashlib, pathlib, subprocess, difflib, re
R=pathlib.Path(__file__).resolve().parent
BASE=R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/stage/FluidX3D_on'
NEW=R/'FluidX3D_on'
FLAGS=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']
def syntax(root):
    subprocess.run(FLAGS+['-fsyntax-only','src/kernel.cpp','src/lbm.cpp','src/setup.cpp'],cwd=root,check=True)
def body(root):
    emit=R/'emit_kernel.cpp'
    emit.write_text('#include "kernel.cpp"\nint main(){std::cout << get_opencl_c_code();}\n')
    exe=R/'emit_kernel'
    subprocess.run(FLAGS+['-Isrc',str(emit),'-o',str(exe)],cwd=root,check=True)
    return subprocess.check_output([exe])
# Both source trees already carry their own defines.hpp. Never edit the baseline.
syntax(BASE)
reference=body(BASE)
print('REFERENCE_SHA',hashlib.sha256(reference).hexdigest(),flush=True)
# Toggle only the new macro for the off comparison and restore it immediately.
defines=NEW/'src/defines.hpp'
original=defines.read_bytes()
assert original.count(b'#define SECOND_LAYER_WM //')==1
try:
    defines.write_bytes(original.replace(b'#define SECOND_LAYER_WM //',b'//#define SECOND_LAYER_WM //'))
    syntax(NEW)
    off=body(NEW)
    (R/'opencl_off_vs_reference.diff').write_text(''.join(difflib.unified_diff(reference.decode().splitlines(keepends=True),off.decode().splitlines(keepends=True))))
    assert off==reference, 'OFF mismatch with executed T4 phaseB_v2 source'
    print('OFF_EXACT_REFERENCE',hashlib.sha256(off).hexdigest(),flush=True)
finally:
    defines.write_bytes(original)
syntax(NEW)
on=body(NEW)
assert on!=off and b'second_layer_partial' in on and b'second_layer_stress' in on
(R/'opencl_on_vs_off.diff').write_text(''.join(difflib.unified_diff(off.decode().splitlines(keepends=True),on.decode().splitlines(keepends=True))))
print('ON_SHA',hashlib.sha256(on).hexdigest(),flush=True)
print('HOST_SYNTAX_OK_BOTH',flush=True)
