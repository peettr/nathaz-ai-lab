from earth2studio.data import HRRR, HRRR_FX
import inspect
print('HRRR doc',inspect.getsource(HRRR)[:6000]);print('FX doc',inspect.getsource(HRRR_FX)[:3000]);print('HRRR var count',len(HRRR.VARIABLES) if hasattr(HRRR,'VARIABLES') else 'unknown')
