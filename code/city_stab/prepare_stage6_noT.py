"""Prepare stage6_noT: stage3 official-profile FP32 no-model with TEMPERATURE disabled.

Only edits defines.hpp (comment out TEMPERATURE). Monitor stays source-off,
enabled at Colab build time as in stage3/stage4. Never alters predecessors.
"""
from pathlib import Path
import shutil, hashlib, json, tarfile
R = Path(__file__).resolve().parent
S = R / 'stage3'
D = R / 'stage6_noT'
assert not D.exists(), D
shutil.copytree(S, D, ignore=shutil.ignore_patterns('bin', 'obj', 'RESULTS', '*.vtk', '*.csv', '*.log'))

p = D / 'FluidX3D/src/defines.hpp'
s = p.read_text()
old = '#define TEMPERATURE // enables temperature extension; set fixed-temperature cells with TYPE_T (similar to EQUILIBRIUM_BOUNDARIES); allocates an extra 32 (FP32) or 18 (FP16) Bytes/cell'
assert s.count(old) == 1, 'TEMPERATURE define line not found verbatim'
s = s.replace(old, '//' + old)
# VOLUME_FORCE / FORCE_FIELD are defined on their own lines and must stay enabled.
for macro in ('VOLUME_FORCE', 'FORCE_FIELD', 'SUBGRID', 'EQUILIBRIUM_BOUNDARIES'):
    line = next(l for l in s.splitlines() if l.startswith('#define ' + macro))
    assert line, macro
p.write_text(s)

manifest = {
    'source': str(S),
    'edit': 'defines.hpp: TEMPERATURE commented out; all other macros unchanged',
    'profile_sha256': hashlib.sha256((D / 'case/wind_bc/profile.dat').read_bytes()).hexdigest(),
    'config_sha256': hashlib.sha256((D / 'case/conf.luwpf').read_bytes()).hexdigest(),
    'defines_sha256': hashlib.sha256((D / 'FluidX3D/src/defines.hpp').read_bytes()).hexdigest(),
    'setup_sha256': hashlib.sha256((D / 'FluidX3D/src/setup.cpp').read_bytes()).hexdigest(),
    'kernel_sha256': hashlib.sha256((D / 'FluidX3D/src/kernel.cpp').read_bytes()).hexdigest(),
}
(R / 'stage6noT_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive = R / 'city_stage6noT_inputs.tar.gz'
assert not archive.exists()
with tarfile.open(archive, 'w:gz') as tar:
    tar.add(D / 'FluidX3D', arcname='FluidX3D')
    tar.add(D / 'case', arcname='case')
manifest['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
(R / 'stage6noT_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
