#!/usr/bin/env python3
"""Patch the frozen round-9 setup.cpp in a fresh VM extraction root only.

The additional field is an online mean of instantaneous |u| sampled at the
same steps and from the same device readback as vector mean. Never derive it
from the magnitude of the vector mean or TKE.
"""
from pathlib import Path
import sys


def patch(source: str) -> str:
    edits = [
        ('const float* u_avg, const float* rho_avg, const float* T_avg, const uchar* flags,',
         'const float* u_avg, const float* speed_scalar_avg, const float* rho_avg, const float* T_avg, const uchar* flags,'),
        ('    write_field("u_avg", u_avg, 3u, u_factor);',
         '    write_field("u_avg", u_avg, 3u, u_factor);\n    write_field("speed_scalar_avg", speed_scalar_avg, 1u, u_factor);'),
        ('        std::vector<float> avg_u;\n        std::vector<float> avg_rho;',
         '        std::vector<float> avg_u;\n        std::vector<float> avg_speed_scalar;\n        std::vector<float> avg_rho;'),
        ('            avg_u.assign((size_t)(Ncells * 3ull), 0.0f);',
         '            avg_u.assign((size_t)(Ncells * 3ull), 0.0f);\n            avg_speed_scalar.assign((size_t)Ncells, 0.0f);'),
        ('            float* u_avg = avg_u.data();\n            float* rho_avg = avg_rho.data();',
         '            float* u_avg = avg_u.data();\n            float* speed_scalar_avg = avg_speed_scalar.data();\n            float* rho_avg = avg_rho.data();'),
        ('                const float uz = lbm.u.z[n];\n                float mean_u',
         '                const float uz = lbm.u.z[n];\n                const float instantaneous_speed = sqrtf(ux*ux + uy*uy + uz*uz);\n                speed_scalar_avg[n] += (instantaneous_speed - speed_scalar_avg[n])*inv_n;\n                float mean_u'),
        ('            std::fill(avg_u.begin(), avg_u.end(), 0.0f);',
         '            std::fill(avg_u.begin(), avg_u.end(), 0.0f);\n            std::fill(avg_speed_scalar.begin(), avg_speed_scalar.end(), 0.0f);'),
        ('                          avg_u.data(), avg_rho.data(), T_avg_ptr, flags_host.data(),',
         '                          avg_u.data(), avg_speed_scalar.data(), avg_rho.data(), T_avg_ptr, flags_host.data(),'),
    ]
    for old, new in edits:
        expected = 2 if old == '            std::fill(avg_u.begin(), avg_u.end(), 0.0f);' else 1
        assert source.count(old) == expected, (old, source.count(old))
        source = source.replace(old, new)
    assert source.count('speed_scalar_avg') >= 5
    return source


def main():
    assert len(sys.argv) == 2, 'usage: patch_scalar_mean.py NEW_EXTRACTION_ROOT'
    path = Path(sys.argv[1])/'core/cfd_core/FluidX3D/src/setup.cpp'
    assert path.is_file(), path
    src = path.read_text()
    out = patch(src)
    path.write_text(out)
    print('NATIVE_SCALAR_MEAN_PATCHED', path, flush=True)


if __name__ == '__main__':
    main()
