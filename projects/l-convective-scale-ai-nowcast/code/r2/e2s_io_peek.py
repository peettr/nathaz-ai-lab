import inspect
from earth2studio.io import MemoryBackend
from earth2studio.data import GFS_FX
print('MEM',inspect.signature(MemoryBackend),'GFSFX',inspect.signature(GFS_FX),flush=True)
