import torch, earth2studio, metpy, os, time
from earth2studio.models.px import Pangu6, FuXi
from earth2studio.data import ARCO
print('VERSIONS',torch.__version__,earth2studio.__version__,metpy.__version__,flush=True)
print('GPU',torch.cuda.get_device_name(),torch.cuda.get_device_properties(0).total_memory,flush=True)
for cls in [Pangu6,FuXi]:
 print('MODEL',cls.__name__,cls.load_default_package(),cls.input_coords if hasattr(cls,'input_coords') else '',flush=True)
print('ARCO',ARCO,flush=True)
