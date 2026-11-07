import inspect
from earth2studio.models.px import StormCast
s=inspect.getsource(StormCast).splitlines()
for i,x in enumerate(s):
 if any(k in x for k in ['conditioning_data_source','get_data','randn','generator','def __call__','def input_coords','def output_coords','def create_iterator','def __init__']):
  print(i+1, '\n'.join(s[max(0,i-2):min(len(s),i+5)]),flush=True)
