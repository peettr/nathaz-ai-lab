"""Static, non-executing pickle opcode audit. Run on CRC before torch/pickle load."""
import pickletools
import sys
import zipfile
from pathlib import Path

ALLOWED = ('torch', 'collections', 'numpy', 'jax', 'jaxlib', 'haiku', 'neuralgcm',
           'dinosaur', 'builtins', '_codecs', 'functools', 'operator', 'copyreg',
           'optax', 'chex', 'xarray', 'pandas', 'datetime', 'types', 'tree', 'etils')

for name in sys.argv[1:]:
    path = Path(name)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [k for k in archive.namelist() if k.endswith('.pkl')]
            if not members: raise RuntimeError(f'No pickle member: {name}')
            content = [archive.read(m) for m in members]
    else:
        members, content = [path.name], [path.read_bytes()]
    for member, blob in zip(members, content):
        print('FILE', name, 'MEMBER', member, 'BYTES', len(blob))
        strings = []
        globals_seen = []
        reduces = []
        for opcode, value, offset in pickletools.genops(blob):
            if opcode.name in ('SHORT_BINUNICODE', 'BINUNICODE', 'UNICODE', 'BINUNICODE8'):
                strings.append(value)
            if opcode.name == 'GLOBAL':
                globals_seen.append((offset, value.replace(' ', '.')))
            elif opcode.name == 'STACK_GLOBAL':
                # This is only a heuristic: a real pickle VM stack auditor is
                # required for strong guarantees on dynamic STACK_GLOBAL.
                globals_seen.append((offset, 'STACK_GLOBAL<' + repr(strings[-2:]) + '>'))
            elif opcode.name == 'REDUCE':
                reduces.append(offset)
        distinct = sorted(set(x for _, x in globals_seen))
        for item in distinct: print('GLOBAL', item)
        print('REDUCE_COUNT', len(reduces), 'OFFSETS', reduces[:20])
        bad = [x for x in distinct if x.startswith('STACK_GLOBAL<') or not x.startswith(tuple(p+'.' for p in ALLOWED))]
        print('REVIEW_REQUIRED', bad)
        if bad: sys.exit(2)
