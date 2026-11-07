import inspect
from earth2studio.run import deterministic
from earth2studio.io import ZarrBackend
from earth2studio.data import ARCO
from earth2studio.models.px import Pangu6,FuXi
for obj in [deterministic, ARCO.__call__,Pangu6.load_model,FuXi.load_model]:
 print('\n###',obj,'\n',inspect.getsource(obj)[:12000],flush=True)
