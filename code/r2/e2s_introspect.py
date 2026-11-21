import inspect,earth2studio
from earth2studio.models.px import StormCast
from earth2studio.run import deterministic
from earth2studio.data import GFS
print('E2S',earth2studio.__version__,'STORM_SIG',inspect.signature(StormCast),'CALL',inspect.signature(StormCast.__call__),'FWD',inspect.signature(StormCast.forward),flush=True)
print('GFS',inspect.signature(GFS),'DET',inspect.signature(deterministic),flush=True)
print('STORM_FILE',inspect.getfile(StormCast),flush=True)
print('METHODS',[x for x in dir(StormCast) if any(k in x.lower() for k in ['seed','sample','noise','forecast','load'])],flush=True)
